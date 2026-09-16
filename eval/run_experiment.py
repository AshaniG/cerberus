#!/usr/bin/env python3
"""
run_experiment.py — M6 evaluation harness.

Compares:
  A) static threshold only (adaptive off)
  B) full Cerberus (adaptive on; ML used when model present)

For each mode: run attack traffic, then flash-crowd traffic, record metrics
from the live API into eval/results/.

Prerequisites: Cerberus stack already running
  sudo python3 backend/serve.py <iface> --port 8080

Usage:
  python3 eval/run_experiment.py --target 192.168.1.10 --api http://127.0.0.1:8080
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = Path(__file__).resolve().parent / "results"
FIGURES = Path(__file__).resolve().parent / "figures"
ATTACK = ROOT / "attack" / "attack_gen.py"
FLASH = ROOT / "attack" / "flashcrowd_gen.py"


def api(base: str, path: str, method: str = "GET", body: dict | None = None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{base}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def snapshot(base: str) -> dict:
    return api(base, "/api/status")


def run_gen(script: Path, target: str, rate: int, duration: int) -> None:
    cmd = [
        sys.executable,
        str(script),
        "--target",
        target,
        "--rate",
        str(rate),
        "--duration",
        str(duration),
    ]
    # Attack often needs root for hping3; try without first.
    print(f"+ {' '.join(cmd)}")
    subprocess.run(cmd, check=False)


def measure_window(base: str, seconds: int) -> dict:
    s0 = snapshot(base)
    time.sleep(seconds)
    s1 = snapshot(base)
    t0, t1 = s0.get("totals", {}), s1.get("totals", {})
    return {
        "delta_seen": int(t1.get("seen", 0) - t0.get("seen", 0)),
        "delta_dropped": int(t1.get("dropped", 0) - t0.get("dropped", 0)),
        "delta_passed": int(t1.get("passed", 0) - t0.get("passed", 0)),
        "threshold_start": s0.get("threshold"),
        "threshold_end": s1.get("threshold"),
        "adaptive": (s1.get("adaptive") or {}).get("enabled"),
    }


def configure(base: str, adaptive: bool, threshold: int) -> None:
    api(base, "/api/adaptive", "POST", {"enabled": adaptive})
    if not adaptive:
        api(base, "/api/threshold", "POST", {"threshold": threshold})
    api(base, "/api/clear", "POST", {})
    time.sleep(1)


def run_mode(base: str, name: str, adaptive: bool, threshold: int, target: str, args) -> dict:
    print(f"\n=== Mode: {name} (adaptive={adaptive}, thr={threshold}) ===")
    configure(base, adaptive, threshold)

    # Attack phase
    print("-- attack phase --")
    proc = subprocess.Popen(
        [
            sys.executable,
            str(ATTACK),
            "--target",
            target,
            "--rate",
            str(args.attack_rate),
            "--duration",
            str(args.attack_duration),
        ]
    )
    attack_m = measure_window(base, args.attack_duration + 2)
    proc.wait(timeout=args.attack_duration + 60)

    api(base, "/api/clear", "POST", {})
    time.sleep(1)

    # Flash-crowd phase (false-positive pressure)
    print("-- flash-crowd phase --")
    proc2 = subprocess.Popen(
        [
            sys.executable,
            str(FLASH),
            "--target",
            target,
            "--rate",
            str(args.flash_rate),
            "--duration",
            str(args.flash_duration),
        ]
    )
    flash_m = measure_window(base, args.flash_duration + 2)
    proc2.wait(timeout=args.flash_duration + 60)

    # Detection proxy: drops during attack should be > 0 for a working filter.
    # FP proxy: drops during flash crowd / seen during flash crowd.
    attack_drops = max(attack_m["delta_dropped"], 0)
    flash_drops = max(flash_m["delta_dropped"], 0)
    flash_seen = max(flash_m["delta_seen"], 1)
    return {
        "mode": name,
        "adaptive": adaptive,
        "static_threshold": threshold,
        "attack": attack_m,
        "flashcrowd": flash_m,
        "detection_drops_attack": attack_drops,
        "false_positive_drops_flash": flash_drops,
        "flash_fp_rate": flash_drops / flash_seen,
    }


def write_outputs(rows: list[dict], stamp: str) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    json_path = RESULTS / f"experiment_{stamp}.json"
    csv_path = RESULTS / f"experiment_{stamp}.csv"
    json_path.write_text(json.dumps(rows, indent=2))

    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "mode",
                "adaptive",
                "static_threshold",
                "detection_drops_attack",
                "false_positive_drops_flash",
                "flash_fp_rate",
                "attack_delta_seen",
                "flash_delta_seen",
                "threshold_end_attack",
                "threshold_end_flash",
            ],
        )
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "mode": r["mode"],
                    "adaptive": r["adaptive"],
                    "static_threshold": r["static_threshold"],
                    "detection_drops_attack": r["detection_drops_attack"],
                    "false_positive_drops_flash": r["false_positive_drops_flash"],
                    "flash_fp_rate": f"{r['flash_fp_rate']:.6f}",
                    "attack_delta_seen": r["attack"]["delta_seen"],
                    "flash_delta_seen": r["flashcrowd"]["delta_seen"],
                    "threshold_end_attack": r["attack"]["threshold_end"],
                    "threshold_end_flash": r["flashcrowd"]["threshold_end"],
                }
            )

    # Simple matplotlib figure when available
    try:
        import matplotlib.pyplot as plt

        labels = [r["mode"] for r in rows]
        det = [r["detection_drops_attack"] for r in rows]
        fp = [r["false_positive_drops_flash"] for r in rows]
        x = range(len(labels))
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.bar([i - 0.15 for i in x], det, width=0.3, label="Attack drops")
        ax.bar([i + 0.15 for i in x], fp, width=0.3, label="Flash-crowd drops (FP proxy)")
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels)
        ax.set_ylabel("Packets")
        ax.set_title("Cerberus M6: static vs adaptive")
        ax.legend()
        fig.tight_layout()
        fig_path = FIGURES / f"experiment_{stamp}.png"
        fig.savefig(fig_path)
        print(f"Wrote {fig_path}")
    except Exception as exc:
        print(f"(plot skipped: {exc})")

    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    return json_path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--api", default="http://127.0.0.1:8080")
    p.add_argument("--target", required=True, help="Host IP that receives traffic / has XDP")
    p.add_argument("--static-threshold", type=int, default=80, help="Harsh static baseline")
    p.add_argument("--attack-rate", type=int, default=300)
    p.add_argument("--attack-duration", type=int, default=15)
    p.add_argument("--flash-rate", type=int, default=120)
    p.add_argument("--flash-duration", type=int, default=20)
    args = p.parse_args()

    # Smoke-check API
    try:
        snapshot(args.api)
    except Exception as exc:
        print(f"Cannot reach API at {args.api}: {exc}", file=sys.stderr)
        print("Start: sudo python3 backend/serve.py <iface>", file=sys.stderr)
        sys.exit(1)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows = [
        run_mode(
            args.api,
            "static_baseline",
            adaptive=False,
            threshold=args.static_threshold,
            target=args.target,
            args=args,
        ),
        run_mode(
            args.api,
            "adaptive_two_tier",
            adaptive=True,
            threshold=args.static_threshold,
            target=args.target,
            args=args,
        ),
    ]
    write_outputs(rows, stamp)
    print("\nSummary:")
    for r in rows:
        print(
            f"  {r['mode']}: attack_drops={r['detection_drops_attack']} "
            f"flash_fp_drops={r['false_positive_drops_flash']} "
            f"fp_rate={r['flash_fp_rate']:.4f}"
        )


if __name__ == "__main__":
    main()
