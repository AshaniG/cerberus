#!/usr/bin/env python3
"""
ddos_loader.py — Milestone M2+: load xdp_ddos.c, expose maps, print top talkers.

WHAT THIS IS
------------
Userspace half of Tier 1. Compiles and attaches kernel/xdp_ddos.c, seeds the
threshold into the `config` BPF map, and every second prints global totals
plus the top source IPs by packet count.

This process must stay running for the XDP program to remain attached.
Later milestones (collector, API, control loop) either co-exist by opening
the same maps via BCC pinned paths, or run *inside* this long-lived process.
For the product shell we keep this loader as the attach owner and expose a
simple Unix status file + optional pin for other processes.

MAP CONTRACT (must match kernel/xdp_ddos.c)
------------------------------------------
  ip_count  hash   u32 src_ip  → u64 count
  config    array  index 0     → u64 threshold
  totals    array  0=seen 1=dropped 2=passed

HOW TO RUN
----------
    sudo python3 loader/ddos_loader.py <interface> [--threshold 250]

Press Ctrl+C to detach.
"""

import argparse
import json
import socket
import struct
import sys
import time
from pathlib import Path

from bcc import BPF

ROOT = Path(__file__).resolve().parent.parent
KERNEL_SRC = ROOT / "kernel" / "xdp_ddos.c"
# Status snapshot written for the collector/API when they cannot share the
# BPF object directly (separate processes). Updated every loop.
STATUS_PATH = ROOT / "data" / "runtime_status.json"
DEFAULT_THRESHOLD = 250


def ip_to_str(n):
    """Convert network-order u32 to dotted IPv4 string."""
    return socket.inet_ntoa(struct.pack("=I", n))


def attach_xdp(b, fn, device):
    flags = 0
    try:
        b.attach_xdp(device, fn, flags)
        mode = "native"
        print(f"Attached to {device} in native XDP mode.")
    except Exception:
        print(f"Native XDP not supported on {device}; retrying in SKB mode ...")
        flags = BPF.XDP_FLAGS_SKB_MODE
        b.attach_xdp(device, fn, flags)
        mode = "skb"
        print(f"Attached to {device} in SKB (generic) XDP mode.")
    return flags, mode


def set_threshold(b, threshold):
    """Write config[0] = threshold (live; no reload)."""
    config = b["config"]
    # BCC array assignment: key index → ctypes c_ulong / int
    config[0] = ctypes_u64(threshold)


def ctypes_u64(value):
    import ctypes

    return ctypes.c_uint64(int(value))


def read_totals(b):
    totals = b["totals"]
    out = {}
    names = ("seen", "dropped", "passed")
    for i, name in enumerate(names):
        try:
            leaf = totals[i]
            out[name] = int(leaf.value) if hasattr(leaf, "value") else int(leaf)
        except KeyError:
            out[name] = 0
    return out


def read_threshold(b):
    try:
        leaf = b["config"][0]
        return int(leaf.value) if hasattr(leaf, "value") else int(leaf)
    except (KeyError, TypeError):
        return DEFAULT_THRESHOLD


def top_ips(b, n=10):
    rows = []
    for k, v in b["ip_count"].items():
        ip_int = k.value if hasattr(k, "value") else int(k)
        count = v.value if hasattr(v, "value") else int(v)
        rows.append({"ip": ip_to_str(ip_int), "ip_int": ip_int, "count": count})
    rows.sort(key=lambda r: r["count"], reverse=True)
    return rows[:n]


def write_status(device, mode, threshold, totals, top):
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "device": device,
        "mode": mode,
        "threshold": threshold,
        "totals": totals,
        "top": top,
        "ts": time.time(),
        "adaptive": False,
        "ml_enabled": False,
    }
    STATUS_PATH.write_text(json.dumps(payload, indent=2))


def clear_maps(b):
    """Zero counters — useful between demo runs."""
    b["ip_count"].clear()
    for i in range(3):
        b["totals"][i] = ctypes_u64(0)


def main():
    parser = argparse.ArgumentParser(description="Cerberus Tier-1 XDP loader")
    parser.add_argument("interface", help="Network interface (e.g. eth0)")
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help=f"Initial drop threshold (default {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--clear-on-start",
        action="store_true",
        help="Zero maps after attach",
    )
    args = parser.parse_args()
    device = args.interface

    print(f"Compiling {KERNEL_SRC} ...")
    b = BPF(src_file=str(KERNEL_SRC))
    fn = b.load_func("xdp_ddos", BPF.XDP)
    flags, mode = attach_xdp(b, fn, device)

    set_threshold(b, args.threshold)
    if args.clear_on_start:
        clear_maps(b)
    print(f"Threshold set to {args.threshold} packets per source IP.")
    print("Printing tops every 1s — press Ctrl+C to stop.\n")

    try:
        while True:
            thr = read_threshold(b)
            totals = read_totals(b)
            top = top_ips(b, 10)
            write_status(device, mode, thr, totals, top)

            print(
                f"seen={totals['seen']} dropped={totals['dropped']} "
                f"passed={totals['passed']} threshold={thr}"
            )
            for row in top[:5]:
                print(f"  {row['ip']:16s}  count={row['count']}")
            if not top:
                print("  (no IPv4 sources counted yet)")
            print()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping ...")
    finally:
        b.remove_xdp(device, flags)
        if STATUS_PATH.exists():
            STATUS_PATH.unlink()
        print(f"Detached from {device}. Done.")


if __name__ == "__main__":
    main()
