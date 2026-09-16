#!/usr/bin/env python3
"""
count_loader.py — Milestone M1: load count_all.c and read the global counter.

WHAT THIS IS
------------
Userspace half of M1. Compiles and attaches kernel/count_all.c at the XDP
hook, then every second reads the `pkt_count` BPF map and prints the total.
Seeing the number climb when traffic arrives is M1's success condition.

HOW TO RUN
----------
    sudo python3 loader/count_loader.py <interface>

Generate traffic (another terminal): ping <this-host> or browse the web.
Press Ctrl+C to detach cleanly.
"""

import sys
import time
from pathlib import Path

from bcc import BPF

KERNEL_SRC = Path(__file__).resolve().parent.parent / "kernel" / "count_all.c"


def attach_xdp(b, fn, device):
    """Try native XDP first; fall back to SKB/generic (Wi-Fi friendly)."""
    flags = 0
    try:
        b.attach_xdp(device, fn, flags)
        print(f"Attached to {device} in native XDP mode.")
    except Exception:
        print(f"Native XDP not supported on {device}; retrying in SKB mode ...")
        flags = BPF.XDP_FLAGS_SKB_MODE
        b.attach_xdp(device, fn, flags)
        print(f"Attached to {device} in SKB (generic) XDP mode.")
    return flags


def main():
    if len(sys.argv) != 2:
        print("Usage: sudo python3 loader/count_loader.py <interface>")
        print("       (list interfaces with: ip link show)")
        sys.exit(1)
    device = sys.argv[1]

    print(f"Compiling {KERNEL_SRC} ...")
    b = BPF(src_file=str(KERNEL_SRC))
    fn = b.load_func("count_all", BPF.XDP)
    flags = attach_xdp(b, fn, device)

    # Map handle: key 0 → u64 packet total (matches BPF_ARRAY in the C file).
    pkt_count = b["pkt_count"]
    print("Reading pkt_count every 1s — press Ctrl+C to stop.\n")

    try:
        prev = 0
        while True:
            key = 0
            # BCC array lookup: leave_as_is keeps the ctypes value object.
            leaf = pkt_count[key]
            total = int(leaf.value) if hasattr(leaf, "value") else int(leaf)
            delta = total - prev
            print(f"packets={total}  (+{delta}/s)")
            prev = total
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping ...")
    finally:
        b.remove_xdp(device, flags)
        print(f"Detached from {device}. Done.")


if __name__ == "__main__":
    main()
