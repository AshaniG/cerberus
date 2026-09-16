#!/usr/bin/env python3
"""
hello_loader.py — Milestone M0: load and attach the hello eBPF/XDP program.

WHAT THIS IS
------------
The userspace half of M0. The kernel half (kernel/hello_xdp.c) is restricted C
that runs per-packet inside the kernel; this script is the BCC loader that
compiles that C *on this machine, right now, for the running kernel* and
attaches it to a network interface at the XDP hook. There is no separate build
step — that on-the-spot compile is exactly why we chose BCC (it avoids
kernel-header version mismatches).

WHY IT EXISTS
-------------
M0 proves the toolchain: if this script reports "attached" and then prints a
line whenever a packet arrives, we know eBPF compiles, passes the kernel's
verifier, and attaches to our NIC. Every later milestone builds on that.

HOW TO RUN IT
-------------
Loading an eBPF program requires root, and BCC lives in the *system* Python
(installed via python3-bpfcc), not the project venv. So:

    sudo python3 loader/hello_loader.py <interface>

Find your interface name with:  ip link show   (prefer a wired interface;
Wi-Fi often lacks native XDP support — we fall back automatically).

Press Ctrl+C to stop. The script detaches the program on exit, so nothing is
left running in the kernel afterwards.
"""

import sys
import time
from pathlib import Path

# BCC's Python bindings. If this import fails, BCC is not installed for the
# system Python — see docs/SETUP_GUIDE.md. Quick check:
#   python3 -c "from bcc import BPF; print('BCC OK')"
from bcc import BPF

# Resolve the path to the C source from THIS file's location, never from the
# current working directory. (Project rule: a past bug had components resolve
# paths from cwd and open different files depending on where they were
# launched. Always anchor paths to __file__.)
KERNEL_SRC = Path(__file__).resolve().parent.parent / "kernel" / "hello_xdp.c"


def main():
    # ---- 1. Which interface? ------------------------------------------------
    # The interface name must be given on the command line, e.g. "eth0" or
    # "enp3s0". We refuse to guess: attaching to the wrong interface would
    # just silently show no packets and waste debugging time.
    if len(sys.argv) != 2:
        print("Usage: sudo python3 loader/hello_loader.py <interface>")
        print("       (list your interfaces with: ip link show)")
        sys.exit(1)
    device = sys.argv[1]

    # ---- 2. Compile the eBPF program ---------------------------------------
    # BPF(src_file=...) hands the C source to BCC, which compiles it for the
    # kernel we are running on right now. If the C has an error, or the
    # kernel's verifier rejects the program, it fails HERE with a compiler /
    # verifier message — before anything touches the network.
    print(f"Compiling {KERNEL_SRC} ...")
    b = BPF(src_file=str(KERNEL_SRC))

    # load_func fetches our compiled function by name and tells the kernel it
    # is an XDP-type program (the kernel checks the type matches the hook).
    fn = b.load_func("hello_xdp", BPF.XDP)

    # ---- 3. Attach at the XDP hook ------------------------------------------
    # Try "native" XDP first (flags=0): the program runs inside the NIC
    # driver itself — the fastest option. Not every driver supports it
    # (Wi-Fi usually doesn't), so if native fails we retry in SKB/"generic"
    # mode, where the kernel runs the program slightly later in software.
    # Slower, but fine for this project: we are measuring detection logic,
    # not raw throughput (see PROJECT_CONTEXT.md §6).
    flags = 0  # 0 = native XDP
    try:
        b.attach_xdp(device, fn, flags)
        print(f"Attached to {device} in native XDP mode.")
    except Exception:
        print(f"Native XDP not supported on {device}; retrying in SKB (generic) mode ...")
        flags = BPF.XDP_FLAGS_SKB_MODE
        b.attach_xdp(device, fn, flags)
        print(f"Attached to {device} in SKB (generic) XDP mode.")

    # ---- 4. Prove it is running ---------------------------------------------
    # The C program writes "hello_xdp: packet seen" into the kernel trace
    # buffer for every packet. We read that buffer here and echo the lines.
    # Seeing them is M0's success condition: our code is genuinely executing
    # in the kernel, once per packet. (Generate traffic with e.g.
    # `ping <this machine>` from another terminal if the interface is quiet.)
    print("Watching for packets — press Ctrl+C to stop.\n")
    try:
        while True:
            # trace_fields() blocks until the next trace line arrives, then
            # returns it split into fields; msg is the text our C wrote.
            (task, pid, cpu, tp_flags, ts, msg) = b.trace_fields()
            print(f"[{ts}] {msg.decode(errors='replace')}")
    except KeyboardInterrupt:
        print("\nStopping ...")
    finally:
        # ---- 5. Always detach on the way out --------------------------------
        # remove_xdp unhooks our program from the interface. Without this, the
        # program would stay attached in the kernel after the script exits.
        # Must use the SAME flags we attached with, or the detach can fail.
        b.remove_xdp(device, flags)
        print(f"Detached from {device}. Done.")


if __name__ == "__main__":
    main()
