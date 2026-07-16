#!/usr/bin/env python3
"""
serve.py — start Cerberus: XDP attach + collector + control loop + FastAPI.

HOW TO RUN (Ubuntu, system Python with BCC, as root)
----------------------------------------------------
    cd /path/to/cerberus
    sudo python3 backend/serve.py eth0 --threshold 250 --port 8080

Then open http://<host>:8080/ for the dashboard.

Press Ctrl+C to stop and detach XDP cleanly.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `sudo python3 backend/serve.py` to resolve `backend` / `ml` packages.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Cerberus full stack")
    parser.add_argument("interface", help="NIC to attach XDP (e.g. eth0)")
    parser.add_argument("--threshold", type=int, default=250)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--no-adaptive", action="store_true", help="Start with adaptive off")
    parser.add_argument("--interval", type=float, default=1.0, help="Collector interval seconds")
    args = parser.parse_args()

    from backend import db, mongo, runtime_state
    from backend.bpf_session import session
    from backend.collector import Collector
    from backend.control_loop import ControlLoop

    db.init_db()
    runtime_state.atlas_connected = mongo.configure_from_env()
    if runtime_state.atlas_connected:
        print("MongoDB Atlas: connected")
    else:
        err = mongo.last_error()
        print("MongoDB Atlas: disabled" + (f" ({err})" if err else " (no MONGODB_URI)"))

    try:
        from ml.classify import model_available

        runtime_state.ml_available = model_available()
    except Exception:
        runtime_state.ml_available = False
    print(f"ML model available: {runtime_state.ml_available}")

    session.attach(args.interface, threshold=args.threshold)
    runtime_state.bpf_session = session

    collector = Collector(session, interval=args.interval)
    collector.start()
    runtime_state.collector = collector

    control = ControlLoop(session, enabled=not args.no_adaptive)
    control.start()
    runtime_state.control_loop = control
    db.set_config(db.init_db(), "adaptive_enabled", "0" if args.no_adaptive else "1")
    db.set_config(db.init_db(), "threshold", str(args.threshold))

    import uvicorn
    from backend.api import app

    print(f"Dashboard: http://{args.host}:{args.port}/")
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    finally:
        print("Shutting down ...")
        control.stop()
        collector.stop()
        session.detach()


if __name__ == "__main__":
    main()
