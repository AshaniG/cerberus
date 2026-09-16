"""
bpf_session.py — shared handle around the Tier-1 XDP program and its maps.

Owns attach/detach and map read/write so collector, control loop, and API
all talk to the *same* BPF object (the map contract in kernel/xdp_ddos.c).
"""

from __future__ import annotations

import ctypes
import socket
import struct
import threading
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
KERNEL_SRC = ROOT / "kernel" / "xdp_ddos.c"
DEFAULT_THRESHOLD = 250


def _u64(value: int) -> ctypes.c_uint64:
    return ctypes.c_uint64(int(value))


def ip_to_str(n: int) -> str:
    return socket.inet_ntoa(struct.pack("=I", int(n)))


class BpfSession:
    """Long-lived XDP session. Thread-safe for map reads/writes."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.b = None
        self.device: Optional[str] = None
        self.mode: Optional[str] = None
        self.flags: int = 0
        self.attached: bool = False
        self.started_at: Optional[float] = None

    def attach(self, device: str, threshold: int = DEFAULT_THRESHOLD) -> None:
        # BCC is system-Python only; import here so non-root API imports still work
        # when mocking / reading SQLite offline.
        from bcc import BPF

        with self._lock:
            if self.attached:
                raise RuntimeError("XDP already attached")
            print(f"Compiling {KERNEL_SRC} ...")
            self.b = BPF(src_file=str(KERNEL_SRC), cflags=["-Wno-return-type"])
            fn = self.b.load_func("xdp_ddos", BPF.XDP)
            flags = 0
            mode = "native"
            try:
                self.b.attach_xdp(device, fn, flags)
            except Exception:
                flags = BPF.XDP_FLAGS_SKB_MODE
                self.b.attach_xdp(device, fn, flags)
                mode = "skb"
            self.device = device
            self.mode = mode
            self.flags = flags
            self.attached = True
            self.started_at = time.time()
            self.set_threshold(threshold)
            print(f"Attached to {device} in {mode} XDP mode (threshold={threshold}).")

    def detach(self) -> None:
        with self._lock:
            if not self.attached or self.b is None or not self.device:
                return
            self.b.remove_xdp(self.device, self.flags)
            self.attached = False
            print(f"Detached from {self.device}.")

    def set_threshold(self, threshold: int) -> None:
        with self._lock:
            if self.b is None:
                raise RuntimeError("BPF not loaded")
            self.b["config"][0] = _u64(threshold)

    def get_threshold(self) -> int:
        with self._lock:
            if self.b is None:
                return DEFAULT_THRESHOLD
            try:
                leaf = self.b["config"][0]
                return int(leaf.value) if hasattr(leaf, "value") else int(leaf)
            except (KeyError, TypeError):
                return DEFAULT_THRESHOLD

    def read_totals(self) -> dict[str, int]:
        with self._lock:
            out = {"seen": 0, "dropped": 0, "passed": 0}
            if self.b is None:
                return out
            names = ("seen", "dropped", "passed")
            for i, name in enumerate(names):
                try:
                    leaf = self.b["totals"][i]
                    out[name] = int(leaf.value) if hasattr(leaf, "value") else int(leaf)
                except KeyError:
                    pass
            return out

    def top_ips(self, n: int = 20, threshold: Optional[int] = None) -> list[dict[str, Any]]:
        with self._lock:
            if self.b is None:
                return []
            thr = threshold if threshold is not None else self.get_threshold()
            rows = []
            for k, v in self.b["ip_count"].items():
                ip_int = k.value if hasattr(k, "value") else int(k)
                count = v.value if hasattr(v, "value") else int(v)
                action = "drop" if count >= thr else "pass"
                rows.append({"ip": ip_to_str(ip_int), "ip_int": ip_int, "count": int(count), "action": action})
            rows.sort(key=lambda r: r["count"], reverse=True)
            return rows[:n]

    def clear_counts(self) -> None:
        with self._lock:
            if self.b is None:
                return
            self.b["ip_count"].clear()
            for i in range(3):
                self.b["totals"][i] = _u64(0)

    def status_dict(self) -> dict[str, Any]:
        totals = self.read_totals()
        thr = self.get_threshold()
        return {
            "attached": self.attached,
            "device": self.device,
            "mode": self.mode,
            "threshold": thr,
            "totals": totals,
            "top": self.top_ips(10, thr),
            "started_at": self.started_at,
            "ts": time.time(),
        }


# Process-wide singleton used by serve.py / API / collector / control loop.
session = BpfSession()
