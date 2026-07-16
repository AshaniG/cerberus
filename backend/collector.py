"""
collector.py — cold-path: read BPF maps on a timer, persist to SQLite (+ Atlas).

Runs in a background thread started by serve.py. Never touches packets on the
hot path — a few times per second is enough for the dashboard and thesis logs.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from backend import db, mongo
from backend.bpf_session import BpfSession


class Collector:
    def __init__(
        self,
        session: BpfSession,
        interval: float = 1.0,
        soft_ratio: float = 0.6,
    ) -> None:
        self.session = session
        self.interval = interval
        # IPs between soft_ratio*threshold and threshold are "ambiguous" (M5).
        self.soft_ratio = soft_ratio
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._prev_dropped: dict[str, int] = {}
        self.conn = db.init_db()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="collector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as exc:  # noqa: BLE001 — keep loop alive
                print(f"[collector] error: {exc}")
            self._stop.wait(self.interval)

    def tick(self) -> None:
        if not self.session.attached:
            return
        totals = self.session.read_totals()
        thr = self.session.get_threshold()
        top = self.session.top_ips(30, thr)
        soft = int(thr * self.soft_ratio)

        db.insert_snapshot(
            self.conn,
            total_pkts=totals["seen"],
            dropped=totals["dropped"],
            passed=totals["passed"],
            threshold=thr,
        )
        if top:
            db.insert_ip_stats(self.conn, top)

        mongo.insert_snapshot(
            {
                "ts": time.time(),
                "total_pkts": totals["seen"],
                "dropped": totals["dropped"],
                "passed": totals["passed"],
                "threshold": thr,
            }
        )

        # Emit drop events when an IP newly crosses threshold.
        for row in top:
            ip = row["ip"]
            count = row["count"]
            prev = self._prev_dropped.get(ip, 0)
            if count >= thr and prev < thr:
                detail = f"count={count} threshold={thr}"
                db.insert_event(self.conn, "drop", ip, detail)
                mongo.insert_event(
                    {"ts": time.time(), "type": "drop", "src_ip": ip, "detail": detail}
                )
            elif soft <= count < thr and prev < soft:
                # Ambiguous band — escalate for Tier-2 ML (M5).
                detail = f"ambiguous count={count} soft={soft} hard={thr}"
                db.insert_event(self.conn, "escalate", ip, detail)
                mongo.insert_event(
                    {
                        "ts": time.time(),
                        "type": "escalate",
                        "src_ip": ip,
                        "detail": detail,
                    }
                )
                self._try_classify(ip, count, thr)
            self._prev_dropped[ip] = count

    def _try_classify(self, ip: str, count: int, thr: int) -> None:
        """Optional M5 hook — no-op if model missing."""
        try:
            from ml.classify import classify_flow

            label, score = classify_flow(
                {
                    "packet_count": count,
                    "threshold": thr,
                    "src_ip": ip,
                }
            )
            detail = f"ml_label={label} score={score:.3f} count={count}"
            db.insert_event(self.conn, "ml", ip, detail)
            mongo.insert_event(
                {"ts": time.time(), "type": "ml", "src_ip": ip, "detail": detail}
            )
        except Exception:
            # Model not trained yet or features unavailable — fine before M5.
            pass
