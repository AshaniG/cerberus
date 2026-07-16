#!/usr/bin/env python3
"""
flashcrowd_gen.py — legitimate surge traffic for false-positive evaluation (M6).

NOVELTY 3: flash crowds look like sudden volume but come from many distinct
"users" with modest per-source rates — exactly what a naive static threshold
misfires on, and what adaptive + selective ML should spare.

This generator opens many short TCP connections / HTTP GETs (or UDP probes)
from the *same* host. For a single-host lab, we simulate diversity by using
many destination ports and pacing so per-flow counts stay below a harsh
static threshold while aggregate volume is high. For a stronger demo, run
from multiple VMs/containers.

    python3 attack/flashcrowd_gen.py --target 192.168.1.10 --rate 150 --duration 40
"""

from __future__ import annotations

import argparse
import concurrent.futures
import random
import socket
import time


def one_client(target: str, port: int, bursts: int, pause: float) -> int:
    ok = 0
    for _ in range(bursts):
        try:
            with socket.create_connection((target, port), timeout=0.8) as s:
                s.sendall(b"GET / HTTP/1.0\r\nHost: cerberus-demo\r\n\r\n")
                try:
                    s.recv(256)
                except socket.timeout:
                    pass
                ok += 1
        except OSError:
            # Port closed is fine — packets still traversed the XDP hook on the path.
            try:
                # UDP probe as backup so *some* packets always hit the NIC path.
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(b"flashcrowd", (target, port))
                sock.close()
                ok += 1
            except OSError:
                pass
        time.sleep(pause)
    return ok


def main() -> None:
    p = argparse.ArgumentParser(description="Cerberus flash-crowd generator")
    p.add_argument("--target", required=True)
    p.add_argument("--rate", type=int, default=150, help="Aggregate attempts/sec goal")
    p.add_argument("--duration", type=int, default=40)
    p.add_argument("--workers", type=int, default=40, help="Parallel 'users'")
    p.add_argument("--ports", default="80,443,8080,8000,22")
    args = p.parse_args()

    ports = [int(x) for x in args.ports.split(",") if x.strip()]
    end = time.time() + args.duration
    # Per-worker pause so aggregate ≈ rate
    pause = max(0.01, args.workers / max(args.rate, 1))
    bursts_each = max(1, int(args.duration / pause))

    print(
        f"Flash crowd → {args.target} workers={args.workers} "
        f"~{args.rate}/s for {args.duration}s (legit-like surge)"
    )
    total = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = []
        while time.time() < end:
            for _ in range(args.workers):
                port = random.choice(ports)
                futs.append(pool.submit(one_client, args.target, port, 1, 0))
            time.sleep(max(0.05, args.workers / max(args.rate, 1)))
            # Drain completed
            done = [f for f in futs if f.done()]
            for f in done:
                try:
                    total += f.result()
                except Exception:
                    pass
                futs.remove(f)
        concurrent.futures.wait(futs, timeout=10)
        for f in futs:
            if f.done():
                try:
                    total += f.result()
                except Exception:
                    pass
    print(f"Flash crowd finished. successful_ops≈{total}")


if __name__ == "__main__":
    main()
