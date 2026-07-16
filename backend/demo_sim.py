"""
demo_sim.py — UI preview counters when XDP is not attached.

On Mac / API-only smoke tests, Start Attack still launches generators, but
packets never hit BPF maps — Seen stays 0 and the UI looks "broken".

While a demo generator is running *and* Tier-1 is offline, this ticker writes
preview snapshots/IP rows so the dashboard visibly reacts. Status carries
`ui_preview=true` so we never confuse this with live XDP numbers.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from backend import db


class DemoSimulator:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.active = False
        self.kind: Optional[str] = None  # attack | flashcrowd
        self.target: str = "127.0.0.1"
        self.rate: int = 100
        self.seen = 0
        self.dropped = 0
        self.passed = 0
        self.threshold = 250
        self.top: list[dict] = []
        self.message = ""

    def start(self, kind: str, target: str, rate: int, threshold: int = 250) -> None:
        with self._lock:
            self.stop_unlocked()
            self.kind = kind
            self.target = target
            self.rate = max(1, int(rate))
            self.threshold = int(threshold)
            self.seen = 0
            self.dropped = 0
            self.passed = 0
            self.active = True
            self.message = (
                f"UI preview: simulating {kind} toward {target} @ ~{self.rate}/s "
                "(Tier-1/XDP not attached — not live kernel counts)"
            )
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="demo_sim", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self.stop_unlocked()

    def stop_unlocked(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None
        self.active = False
        self.kind = None
        self.message = ""

    def _run(self) -> None:
        conn = db.init_db()
        attacker = self.target if self.kind == "attack" else None
        # Flash crowd: several modest IPs; attack: one heavy IP.
        while not self._stop.is_set():
            if self.kind == "attack":
                burst = max(5, self.rate // 2)
                self.seen += burst
                # After crossing threshold, most new packets "drop" in preview.
                if self.seen > self.threshold:
                    d = int(burst * 0.7)
                    p = burst - d
                else:
                    d, p = 0, burst
                self.dropped += d
                self.passed += p
                count = self.seen
                action = "drop" if count >= self.threshold else "pass"
                self.top = [
                    {"ip": attacker or "10.0.0.99", "count": count, "action": action},
                    {"ip": "10.0.0.2", "count": max(1, count // 20), "action": "pass"},
                ]
            else:
                burst = max(8, self.rate // 3)
                self.seen += burst
                self.passed += burst
                # Flash crowd: many sources under threshold → few drops in preview.
                self.top = [
                    {"ip": f"10.1.0.{i}", "count": max(3, self.rate // 10 + i), "action": "pass"}
                    for i in range(1, 8)
                ]
                if self.rate > 400:
                    self.dropped += 1

            db.insert_snapshot(
                conn,
                total_pkts=self.seen,
                dropped=self.dropped,
                passed=self.passed,
                threshold=self.threshold,
            )
            db.insert_ip_stats(conn, self.top)
            self._stop.wait(1.0)

    def status_overlay(self) -> dict:
        return {
            "ui_preview": self.active,
            "preview_kind": self.kind,
            "preview_message": self.message,
            "totals": {
                "seen": self.seen,
                "dropped": self.dropped,
                "passed": self.passed,
            },
            "top": self.top,
            "threshold": self.threshold,
        }


simulator = DemoSimulator()
