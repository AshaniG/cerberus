# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Cerberus is a **research prototype** (final-year BSc dissertation) for kernel-level,
two-tier, online-adaptive DDoS detection using eBPF/XDP. It is **not** a production
product. `docs/PROJECT_CONTEXT.md` is the single source of truth — read it before
touching code. `docs/FOLDER_LAYOUT.md` is the target repo shape; `docs/SETUP_GUIDE.md`
is the environment setup.

The repo is currently **docs-only**. Code does not exist yet — it is created milestone
by milestone (see Build order). Folders appear as their milestone arrives; do not
scaffold the whole tree up front.

## Architecture (the mental model that spans files)

Two tiers split across the kernel/userspace boundary:

- **Tier 1 — hot path (kernel).** An eBPF program attached at the **XDP hook** runs
  per-packet as verified bytecode, the earliest and fastest checkpoint (before the
  normal networking stack). It does cheap statistical filtering: parse source IP,
  count per-IP in a BPF hash map, `XDP_DROP` over a threshold. Lives in `kernel/*.c`
  (restricted C).
- **Tier 2 — cold path (userspace).** Python services (collector, control loop, CLI,
  dashboard) plus a scikit-learn decision tree. Runs a few times per second, off the
  packet path, so **Python's speed is irrelevant here** — do not optimize it.

**BPF maps are the *only* bridge between the two worlds.** The kernel writes packet
counts in; userspace reads them out. Userspace writes a new threshold in; the kernel
reads it on the next packet. This is what makes live, reload-free threshold updates
possible — the defining mechanism of the project.

**Coupling consequence (why this is a monorepo):** the BPF map layout is a shared
contract. Editing a map in `kernel/xdp_ddos.c` forces matching edits in its loader
(`loader/ddos_loader.py`) and in `backend/collector.py`, because all three read the
same map. Change them together in one commit — never let them drift.

## The three novelties — protect these, simplify everything else

The contribution is the *combination* of three things (each maps to a late milestone):

1. **Adaptive, learned threshold updated without reload** (M4) — control loop pushes
   new thresholds into the BPF map live, no XDP reload.
2. **Selective in-kernel ML escalation** (M5) — cheap filter runs in-kernel on *all*
   traffic; only the small ambiguous slice escalates to the userspace decision tree.
3. **Flash-crowd false-positive evaluation** (M6) — deliberately generate *legitimate*
   surge traffic and measure false positives against it, not just attack detection.
   This is the strongest, most defensible novelty.

When a scope decision is ambiguous, protect these three and keep the well-trodden
parts (packet counting, threshold dropping) deliberately standard. **Scope creep is
the main failure mode** — build the minimum system that produces the comparison the
research question asks for. Do not chase production hardening, multi-node, max
throughput, every attack type, or a large ML model.

## Build order (bottom-up; each milestone must run before the next)

Never write a large untested pile of code — build and verify one milestone at a time.

| Milestone | Deliverable | New files |
|---|---|---|
| M0 | Hello eBPF: attach at XDP, pass all packets (do first, day one — collapses setup risk) | `kernel/hello_xdp.c`, `loader/hello_loader.py` |
| M1 | Global packet counter in a BPF map, read from Python | `kernel/count_all.c`, `loader/count_loader.py` |
| M2 | Per-source-IP count + `XDP_DROP` over threshold (Tier 1 core) | `kernel/xdp_ddos.c`, `loader/ddos_loader.py` |
| M3 | Collector → SQLite, `ddosctl` CLI, HTML+Chart.js dashboard | `backend/{collector,db}.py`, `cli/ddosctl.py`, `dashboard/` |
| M4 | Adaptive threshold control loop (novelty 1) | `backend/control_loop.py` |
| M5 | Decision tree trained on CIC-IDS-2017, scores ambiguous slice (novelty 2) | `ml/`, `requirements.txt`, `data/cic-ids-2017/` |
| M6 | Attack + flash-crowd traffic, measure, compare vs static baseline (novelty 3) | `attack/`, `eval/` |

## Commands & environment

Target platform is **bare-metal Ubuntu 24.04 LTS** (not the newest release — the eBPF
toolchain is more stable there). eBPF/BCC does not run on Windows/WSL for this project;
the current dev machine holds the repo but the code runs on the Ubuntu host.

- **Loading an eBPF program requires root** — loaders run as `sudo python3 loader/<x>.py`.
  BCC compiles the `.c` on the machine at load time (no separate build step), which is
  why kernel headers must match the running kernel.
- **Two Python environments, deliberately separate:**
  - BCC uses the **system Python** (`python3-bpfcc` is installed system-wide) — the
    loaders and anything importing `from bcc import BPF` run under system Python, not a venv.
  - The **ML/analysis side** (`scikit-learn`, `pandas`, `numpy`, `joblib`) runs in a
    project **venv**. Keep these worlds apart.
- **Verify the toolchain:** `python3 -c "from bcc import BPF; print('BCC OK')"`
- **Inspect loaded programs/maps:** `sudo bpftool prog show`, `sudo bpftool map show`
- **Find the interface to attach XDP to:** `ip link show` (prefer a wired interface;
  Wi-Fi often lacks native XDP — fall back to SKB/generic XDP mode).
- **Attack traffic:** `hping3`. There is no test framework or linter configured yet;
  "testing" a milestone means running its loader/script and observing the maps/DB/CLI.

## Non-obvious rules

- **`backend/db.py` must resolve the SQLite path from `__file__`, not the cwd.** A past
  bug had the collector and CLI open *different* database files depending on where they
  were launched. Every component must open the same DB.
- **The eBPF verifier is a hard constraint.** It rejects unbounded loops and programs
  over its instruction limit. This is *why* Tier 2 is a bounded decision tree, not a
  neural network. If the verifier rejects a tree, shrink its depth — the contribution is
  the *architecture*, not model size.
- **Comment generously and explain *why*.** The author has near-zero prior programming
  experience. Prefer clear over clever; this preference already drove tooling choices
  (SQLite over InfluxDB, plain HTML/Chart.js over React, BCC over libbpf/Go).
- **`data/`, `*.db`, and model binaries (`ml/model/*.joblib`) are gitignored** — large
  datasets and constantly-changing state do not belong in version control.
