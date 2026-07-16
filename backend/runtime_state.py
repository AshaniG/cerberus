"""
runtime_state.py — shared flags for API / dashboard (attack demo, adaptive, ml).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent

# Filled by serve.py at startup.
bpf_session = None
collector = None
control_loop = None
attack_proc: Optional[subprocess.Popen] = None
flash_proc: Optional[subprocess.Popen] = None
ml_available: bool = False
atlas_connected: bool = False


def _xdp_attached() -> bool:
    sess = bpf_session
    return bool(sess and getattr(sess, "attached", False))


def ensure_preview_for_demo(kind: str, target: str, rate: int) -> None:
    """Start UI preview counters when generators run without live XDP."""
    from backend.demo_sim import simulator

    if _xdp_attached():
        simulator.stop()
        return
    thr = 250
    sess = bpf_session
    if sess:
        try:
            thr = sess.get_threshold()
        except Exception:
            pass
    simulator.start(kind, target, rate, threshold=thr)


def stop_preview_if_idle() -> None:
    from backend.demo_sim import simulator

    attack_on = attack_proc is not None and attack_proc.poll() is None
    flash_on = flash_proc is not None and flash_proc.poll() is None
    if not attack_on and not flash_on:
        simulator.stop()


def public_status() -> dict[str, Any]:
    from backend import mongo
    from backend.bpf_session import session as default_session
    from backend.demo_sim import simulator

    sess = bpf_session or default_session
    attached = bool(sess and sess.attached)
    if attached:
        base = sess.status_dict()
    else:
        base = {
            "attached": False,
            "device": None,
            "mode": None,
            "threshold": simulator.threshold if simulator.active else 250,
            "totals": {"seen": 0, "dropped": 0, "passed": 0},
            "top": [],
            "ts": None,
            "started_at": None,
        }

    # Overlay UI preview when XDP is offline but a demo generator is active.
    ui_preview = (not attached) and simulator.active
    if ui_preview:
        ov = simulator.status_overlay()
        base["totals"] = ov["totals"]
        base["top"] = ov["top"]
        base["threshold"] = ov["threshold"]

    # Reap finished demo processes so badges clear.
    global attack_proc, flash_proc
    if attack_proc is not None and attack_proc.poll() is not None:
        attack_proc = None
    if flash_proc is not None and flash_proc.poll() is not None:
        flash_proc = None
    stop_preview_if_idle()

    attack_on = attack_proc is not None and attack_proc.poll() is None
    flash_on = flash_proc is not None and flash_proc.poll() is None

    cl = control_loop
    adaptive = cl.status() if cl else {"enabled": False}

    mode_label = "live_xdp" if attached else ("ui_preview" if ui_preview else "api_only")
    help_msg = (
        "Live XDP attached — Seen/Dropped are real kernel counters."
        if attached
        else (
            "UI preview active — chart moves while demo traffic runs, but these are NOT "
            "kernel XDP counts. On Ubuntu run: sudo python3 backend/serve.py <iface>"
            if ui_preview
            else "API-only mode (no XDP). Start Attack still works as a generator, but "
            "Seen stays 0 until Tier-1 is attached on Ubuntu."
        )
    )

    return {
        **base,
        "adaptive": adaptive,
        "ml_available": ml_available,
        "atlas_connected": bool(atlas_connected and mongo.is_enabled()),
        "atlas_error": mongo.last_error(),
        "attack_running": attack_on,
        "flashcrowd_running": flash_on,
        "xdp_live": attached,
        "ui_preview": ui_preview,
        "mode_label": mode_label,
        "help_message": help_msg,
        "preview_kind": simulator.kind if ui_preview else None,
    }
