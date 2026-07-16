#!/usr/bin/env python3
"""
ddosctl — operator CLI for Cerberus (status / top / watch / threshold / clear).

Reads SQLite (and live status when the full stack is running via API if
CERBERUS_API is set). Works offline against the local DB alone.

    python3 cli/ddosctl.py status
    python3 cli/ddosctl.py top
    python3 cli/ddosctl.py watch
    python3 cli/ddosctl.py threshold 300
    python3 cli/ddosctl.py clear
    python3 cli/ddosctl.py events
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API = os.environ.get("CERBERUS_API", "http://127.0.0.1:8080").rstrip("/")


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
        print(json.dumps(s, indent=2))
        return
    except Exception:
        pass
    from backend import db

    conn = db.init_db()
    thr = db.get_config(conn, "threshold", "?")
    adaptive = db.get_config(conn, "adaptive_enabled", "?")
    snaps = db.recent_snapshots(conn, 1)
    print(f"threshold={thr} adaptive={adaptive}")
    if snaps:
        print(dict(snaps[-1]))
    else:
        print("(no snapshots yet — is serve.py running?)")


def cmd_top(args: argparse.Namespace) -> None:
    try:
        data = api_get(f"/api/top?limit={args.limit}")
        for row in data.get("top", []):
            ip = row.get("ip") or row.get("src_ip")
            print(f"{ip:16s}  count={row.get('count')}  action={row.get('action', '')}")
        return
    except Exception:
        pass
    from backend import db

    conn = db.init_db()
    for row in db.latest_ip_stats(conn, args.limit):
        print(f"{row['src_ip']:16s}  count={row['count']}  action={row['action']}")


def cmd_watch(args: argparse.Namespace) -> None:
    try:
        while True:
            s = api_get("/api/status")
            t = s.get("totals", {})
            print(
                f"seen={t.get('seen')} dropped={t.get('dropped')} "
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
        data = api_get(f"/api/events?limit={args.limit}")
        for e in data.get("events", []):
            print(f"{e.get('ts')}  {e.get('type'):12s}  {e.get('src_ip') or '-':16s}  {e.get('detail')}")
        return
    except Exception:
        pass
    from backend import db

    conn = db.init_db()
    for e in db.recent_events(conn, args.limit):
        print(f"{e['ts']}  {e['type']:12s}  {e.get('src_ip') or '-':16s}  {e.get('detail')}")


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

    args = p.parse_args()
    {
        "status": cmd_status,
        "top": cmd_top,
        "watch": cmd_watch,
        "threshold": cmd_threshold,
        "clear": cmd_clear,
        "events": cmd_events,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
