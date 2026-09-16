"""
control_loop.py — Milestone M4: adaptive threshold via live BPF map writes.

NOVELTY 1: compute a new threshold from recent traffic and push it into the
kernel `config` map — no XDP reload. The next packet sees the new value.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from backend import db, mongo
from backend.bpf_session import BpfSession, DEFAULT_THRESHOLD


class ControlLoop:
    def __init__(
        self,
        session: BpfSession,
        interval: float = 2.0,
        enabled: bool = True,
        min_threshold: int = 50,
        max_threshold: int = 5000,
        margin: float = 1.5,
        ewma_alpha: float = 0.3,
    ) -> None:
        self.session = session
        self.interval = interval
        self.enabled = enabled
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold
        self.margin = margin
        self.ewma_alpha = ewma_alpha
        self._ewma_rate: Optional[float] = None
        self._prev_seen: Optional[int] = None
        self._prev_ts: Optional[float] = None
        self.last_update_ts: Optional[float] = None
        self.last_threshold: Optional[int] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.conn = db.init_db()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="control_loop", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        db.set_config(self.conn, "adaptive_enabled", "1" if enabled else "0")
        db.insert_event(
            self.conn,
            "adaptive",
            detail=f"adaptive={'on' if enabled else 'off'}",
        )

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if self.enabled and self.session.attached:
                    self.tick()
            except Exception as exc:  # noqa: BLE001
                print(f"[control_loop] error: {exc}")
            self._stop.wait(self.interval)

    def tick(self) -> None:
        totals = self.session.read_totals()
        now = time.time()
        seen = totals["seen"]

        if self._prev_seen is None or self._prev_ts is None:
            self._prev_seen = seen
            self._prev_ts = now
            return

        dt = max(now - self._prev_ts, 1e-3)
        rate = (seen - self._prev_seen) / dt  # packets per second (global)
        self._prev_seen = seen
        self._prev_ts = now

        if self._ewma_rate is None:
            self._ewma_rate = rate
        else:
            a = self.ewma_alpha
            self._ewma_rate = a * rate + (1 - a) * self._ewma_rate

        # Per-IP threshold: use EWMA global rate scaled down + margin.
        # Also look at current top talker so we sit above typical legit bursts.
        top = self.session.top_ips(5)
        top_count = top[0]["count"] if top else 0
        # Convert EWMA pps into a per-window-ish budget: interval-scaled.
        baseline = max(self._ewma_rate * self.interval, 1.0)
        candidate = int(max(baseline, top_count * 0.5) * self.margin)
        candidate = max(self.min_threshold, min(self.max_threshold, candidate))

        current = self.session.get_threshold()
        # Only write when it meaningfully changes — cuts map churn / event spam.
        if abs(candidate - current) < max(5, int(current * 0.05)):
            return

        self.session.set_threshold(candidate)
        self.last_threshold = candidate
        self.last_update_ts = now
        detail = f"threshold {current} -> {candidate} (ewma_pps={self._ewma_rate:.1f})"
        db.set_config(self.conn, "threshold", str(candidate))
        db.insert_event(self.conn, "threshold", detail=detail)
        mongo.insert_event(
            {"ts": now, "type": "threshold", "src_ip": None, "detail": detail}
        )
        print(f"[control_loop] {detail}")

    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "last_update_ts": self.last_update_ts,
            "last_threshold": self.last_threshold,
            "ewma_pps": self._ewma_rate,
            "min_threshold": self.min_threshold,
            "max_threshold": self.max_threshold,
            "default": DEFAULT_THRESHOLD,
        }
