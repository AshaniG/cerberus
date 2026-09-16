"""
api.py — FastAPI backend for the Cerberus ops dashboard.

Serves REST endpoints and the static dashboard. Intended to run inside
serve.py alongside the XDP session (same process = same BPF maps).
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import db, mongo, runtime_state

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = ROOT / "dashboard"

app = FastAPI(title="Cerberus", version="0.1.0", description="Two-tier adaptive DDoS (eBPF/XDP)")


class ThresholdBody(BaseModel):
    threshold: int = Field(..., ge=1, le=1_000_000)


class AdaptiveBody(BaseModel):
    enabled: bool


class AttackBody(BaseModel):
    target: str = Field(..., description="Victim IP (usually this host)")
    rate: int = Field(100, ge=1, le=10000, description="packets per second approx")
    duration: int = Field(30, ge=1, le=600)


@app.get("/api/status")
def api_status():
    return runtime_state.public_status()


@app.get("/api/top")
def api_top(limit: int = 20):
    status = runtime_state.public_status()
    if status.get("ui_preview") and status.get("top"):
        return {"top": status["top"][:limit], "source": "ui_preview"}
    sess = runtime_state.bpf_session
    if sess and sess.attached:
        return {"top": sess.top_ips(limit), "source": "xdp"}
    conn = db.init_db()
    return {"top": db.latest_ip_stats(conn, limit), "source": "sqlite"}


@app.get("/api/events")
def api_events(limit: int = 50):
    conn = db.init_db()
    return {"events": db.recent_events(conn, limit)}


@app.get("/api/timeseries")
def api_timeseries(limit: int = 120):
    conn = db.init_db()
    snaps = db.recent_snapshots(conn, limit)
    return {"points": snaps}


@app.post("/api/threshold")
def api_set_threshold(body: ThresholdBody):
    sess = runtime_state.bpf_session
    if not sess or not sess.attached:
        raise HTTPException(400, "XDP session not attached")
    # Manual set disables adaptive until re-enabled (operator intent).
    if runtime_state.control_loop:
        runtime_state.control_loop.set_enabled(False)
    old = sess.get_threshold()
    sess.set_threshold(body.threshold)
    conn = db.init_db()
    db.set_config(conn, "threshold", str(body.threshold))
    detail = f"manual threshold {old} -> {body.threshold}"
    db.insert_event(conn, "threshold", detail=detail)
    mongo.insert_event({"ts": time.time(), "type": "threshold", "detail": detail})
    return {"ok": True, "threshold": body.threshold}


@app.post("/api/adaptive")
def api_adaptive(body: AdaptiveBody):
    cl = runtime_state.control_loop
    if not cl:
        raise HTTPException(400, "Control loop not running")
    cl.set_enabled(body.enabled)
    return {"ok": True, "enabled": body.enabled}


@app.post("/api/clear")
def api_clear():
    sess = runtime_state.bpf_session
    if not sess or not sess.attached:
        raise HTTPException(400, "XDP session not attached")
    sess.clear_counts()
    conn = db.init_db()
    db.insert_event(conn, "clear", detail="counters cleared")
    return {"ok": True}


def _stop_proc(attr: str) -> None:
    proc = getattr(runtime_state, attr, None)
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    setattr(runtime_state, attr, None)


@app.post("/api/demo/attack/start")
def attack_start(body: AttackBody):
    _stop_proc("attack_proc")
    _stop_proc("flash_proc")
    script = ROOT / "attack" / "attack_gen.py"
    cmd = [
        sys.executable,
        str(script),
        "--target",
        body.target,
        "--rate",
        str(body.rate),
        "--duration",
        str(body.duration),
    ]
    runtime_state.attack_proc = subprocess.Popen(cmd)
    runtime_state.ensure_preview_for_demo("attack", body.target, body.rate)
    conn = db.init_db()
    db.insert_event(
        conn,
        "demo_attack",
        detail=f"start target={body.target} rate={body.rate} duration={body.duration}",
    )
    preview = not runtime_state._xdp_attached()
    return {
        "ok": True,
        "pid": runtime_state.attack_proc.pid,
        "ui_preview": preview,
        "note": (
            "Generator started. UI preview counters will move (XDP not attached)."
            if preview
            else "Generator started. Watch live XDP Seen/Dropped."
        ),
    }


@app.post("/api/demo/attack/stop")
def attack_stop():
    _stop_proc("attack_proc")
    runtime_state.stop_preview_if_idle()
    return {"ok": True}


@app.post("/api/demo/flashcrowd/start")
def flash_start(body: AttackBody):
    _stop_proc("flash_proc")
    _stop_proc("attack_proc")
    script = ROOT / "attack" / "flashcrowd_gen.py"
    cmd = [
        sys.executable,
        str(script),
        "--target",
        body.target,
        "--rate",
        str(body.rate),
        "--duration",
        str(body.duration),
    ]
    runtime_state.flash_proc = subprocess.Popen(cmd)
    runtime_state.ensure_preview_for_demo("flashcrowd", body.target, body.rate)
    conn = db.init_db()
    db.insert_event(conn, "demo_flashcrowd", detail=f"start target={body.target}")
    preview = not runtime_state._xdp_attached()
    return {
        "ok": True,
        "pid": runtime_state.flash_proc.pid,
        "ui_preview": preview,
        "note": (
            "Flash crowd started. UI preview counters will move (XDP not attached)."
            if preview
            else "Flash crowd started — watch live counters."
        ),
    }


@app.post("/api/demo/flashcrowd/stop")
def flash_stop():
    _stop_proc("flash_proc")
    runtime_state.stop_preview_if_idle()
    return {"ok": True}


@app.get("/api/atlas/events")
def atlas_events(limit: int = 20):
    return {"enabled": mongo.is_enabled(), "events": mongo.recent_events(limit)}


@app.get("/")
def index():
    index_path = DASHBOARD_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(404, "dashboard/index.html missing")
    return FileResponse(index_path)


# Static assets (css/js) under /static
if DASHBOARD_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(DASHBOARD_DIR)), name="static")
