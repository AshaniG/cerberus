#!/usr/bin/env python3
"""
ddosctl — operator CLI for Cerberus (status / top / watch / threshold / clear / attack).

Reads SQLite (and live status when the full stack is running via API if
CERBERUS_API is set). Works offline against the local DB alone.

    python3 cli/ddosctl.py status
    python3 cli/ddosctl.py top
    python3 cli/ddosctl.py watch
    python3 cli/ddosctl.py threshold 300
    python3 cli/ddosctl.py clear
    python3 cli/ddosctl.py events
    python3 cli/ddosctl.py attack
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API = os.environ.get("CERBERUS_API", "http://127.0.0.1:8080").rstrip("/")


class C:
    """ANSI colour codes — simple terminal UI, no extra library needed."""
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def _color_action(action: str) -> str:
    color = C.RED if action == "drop" else C.GREEN
    return f"{color}{action}{C.RESET}"


def _color_event_type(event_type: str) -> str:
    if event_type == "drop":
        return f"{C.RED}{event_type:12s}{C.RESET}"
    if event_type == "ml":
        return f"{C.YELLOW}{event_type:12s}{C.RESET}"
    return f"{event_type:12s}"


def _fmt_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _print_kv_block(title: str, rows: list[tuple[str, object]]) -> None:
    print(f"{C.BOLD}{title}{C.RESET}")
    print("-" * len(title))
    width = max(len(k) for k, _ in rows)
    for key, value in rows:
        print(f"{key:<{width}} : {value}")


def _banner() -> None:
    title = "CERBERUS  -  DDoS Control"
    line = "-" * (len(title) + 4)
    print(f"{C.BOLD}{C.GREEN}+{line}+{C.RESET}")
    print(f"{C.BOLD}{C.GREEN}|  {title}  |{C.RESET}")
    print(f"{C.BOLD}{C.GREEN}+{line}+{C.RESET}")


def api_get(path: str):
    url = f"{API}{path}"
    with urllib.request.urlopen(url, timeout=3) as resp:
        return json.loads(resp.read().decode())


def api_post(path: str, body: dict | None = None):
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())


def cmd_status(_: argparse.Namespace) -> None:
    try:
        s = api_get("/api/status")
        totals = s.get("totals", {})
        rows = [
            ("Attached", "yes" if s.get("attached") else "no"),
            ("Threshold", s.get("threshold")),
            ("Adaptive", "on" if s.get("adaptive", {}).get("enabled") else "off"),
            ("Seen", totals.get("seen")),
            ("Dropped", totals.get("dropped")),
            ("Passed", totals.get("passed")),
        ]
        _print_kv_block("CERBERUS STATUS", rows)
        return
    except Exception:
        pass
    from backend import db

    conn = db.init_db()
    thr = db.get_config(conn, "threshold", "?")
    adaptive = db.get_config(conn, "adaptive_enabled", "0")
    snaps = db.recent_snapshots(conn, 1)
    if not snaps:
        print("(no snapshots yet — is serve.py running?)")
        return
    snap = snaps[-1]
    rows = [
        ("Threshold", thr),
        ("Adaptive", "on" if str(adaptive) == "1" else "off"),
        ("Total packets", snap["total_pkts"]),
        ("Dropped", snap["dropped"]),
        ("Passed", snap["passed"]),
        ("Last update", _fmt_ts(snap["ts"])),
    ]
    _print_kv_block("CERBERUS STATUS (offline / last saved)", rows)


def cmd_top(args: argparse.Namespace) -> None:
    try:
        rows = api_get(f"/api/top?limit={args.limit}").get("top", [])
    except Exception:
        from backend import db

        conn = db.init_db()
        rows = db.latest_ip_stats(conn, args.limit)

    if not rows:
        print("(no traffic recorded yet)")
        return

    print(f"{C.BOLD}{'SOURCE IP':16s}  {'COUNT':>8s}  ACTION{C.RESET}")
    for row in rows:
        ip = row.get("ip") or row.get("src_ip")
        action = row.get("action", "")
        print(f"{ip:16s}  {row.get('count'):>8}  {_color_action(action)}")


def cmd_watch(args: argparse.Namespace) -> None:
    try:
        while True:
            s = api_get("/api/status")
            t = s.get("totals", {})
            dropped = t.get("dropped", 0)
            dcolor = C.RED if dropped else C.GREEN
            print(
                f"seen={t.get('seen')} {dcolor}dropped={dropped}{C.RESET} "
                f"passed={t.get('passed')} thr={s.get('threshold')} "
                f"adaptive={s.get('adaptive', {}).get('enabled')}"
            )
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print()
    except Exception as exc:
        print(f"API unreachable ({exc}); start: sudo python3 backend/serve.py <iface>")


def cmd_threshold(args: argparse.Namespace) -> None:
    try:
        print(api_post("/api/threshold", {"threshold": args.value}))
    except Exception as exc:
        print(f"Failed: {exc}")
        sys.exit(1)


def cmd_clear(_: argparse.Namespace) -> None:
    try:
        print(api_post("/api/clear", {}))
    except Exception as exc:
        print(f"Failed: {exc}")
        sys.exit(1)


def cmd_events(args: argparse.Namespace) -> None:
    try:
        events = api_get(f"/api/events?limit={args.limit}").get("events", [])
    except Exception:
        from backend import db

        conn = db.init_db()
        events = db.recent_events(conn, args.limit)

    if not events:
        print("(no events recorded yet)")
        return

    print(f"{C.BOLD}{'TIME':19s}  {'TYPE':12s}  {'SOURCE IP':16s}  DETAIL{C.RESET}")
    for e in events:
        ts = _fmt_ts(e["ts"])
        print(f"{ts:19s}  {_color_event_type(e['type'])}  {(e.get('src_ip') or '-'):16s}  {e.get('detail')}")


def cmd_attack(args: argparse.Namespace) -> None:
    """Look at the recent traffic and say plainly whether an attack is happening now."""
    try:
        points = api_get(f"/api/timeseries?limit={args.window}").get("points", [])
        top = api_get(f"/api/top?limit=30").get("top", [])
    except Exception:
        from backend import db

        conn = db.init_db()
        points = db.recent_snapshots(conn, args.window)
        top = db.latest_ip_stats(conn, 30)

    if len(points) < 2:
        print("Not enough data yet to judge — is the collector running?")
        return

    first, last = points[0], points[-1]
    d_total = last["total_pkts"] - first["total_pkts"]
    d_dropped = last["dropped"] - first["dropped"]
    drop_rate = (d_dropped / d_total * 100) if d_total > 0 else 0.0

    blocked = [row for row in top if row.get("action") == "drop"]
    is_attack = drop_rate >= args.rate_threshold or bool(blocked)

    if is_attack:
        print(f"{C.RED}{C.BOLD}[!] ATTACK LIKELY{C.RESET}")
    else:
        print(f"{C.GREEN}{C.BOLD}[OK] No attack detected{C.RESET}")

    print(f"    recent drop rate: {drop_rate:.1f}%  (last {len(points)} samples)")
    if blocked:
        print(f"    {len(blocked)} source IP(s) currently being dropped:")
        for row in blocked[:10]:
            ip = row.get("ip") or row.get("src_ip")
            print(f"      {C.RED}{ip:16s} count={row.get('count')}{C.RESET}")


def main() -> None:
    p = argparse.ArgumentParser(prog="ddosctl", description="Cerberus operator CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show system status")
    top = sub.add_parser("top", help="Top source IPs")
    top.add_argument("--limit", type=int, default=15)
    watch = sub.add_parser("watch", help="Live totals")
    watch.add_argument("--interval", type=float, default=1.0)
    thr = sub.add_parser("threshold", help="Set threshold (disables adaptive)")
    thr.add_argument("value", type=int)
    sub.add_parser("clear", help="Clear BPF counters")
    ev = sub.add_parser("events", help="Recent events")
    ev.add_argument("--limit", type=int, default=30)
    atk = sub.add_parser("attack", help="Check whether an attack is happening right now")
    atk.add_argument("--window", type=int, default=10, help="how many recent samples to look at")
    atk.add_argument("--rate-threshold", type=float, default=5.0, help="drop rate %% to call it an attack")

    args = p.parse_args()
    _banner()
    {
        "status": cmd_status,
        "top": cmd_top,
        "watch": cmd_watch,
        "threshold": cmd_threshold,
        "clear": cmd_clear,
        "events": cmd_events,
        "attack": cmd_attack,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
