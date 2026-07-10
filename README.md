# Cerberus

**Kernel-level, two-tier, online-adaptive DDoS detection using eBPF/XDP.**

A cheap statistical filter runs in the Linux kernel at the XDP hook (Tier 1);
only ambiguous traffic escalates to a small ML decision tree in userspace
(Tier 2); a userspace control loop updates detection thresholds live via BPF maps
**without reloading** the kernel program. The research shows this design keeps
false positives low against legitimate flash-crowd surges while still detecting
real attacks — beating a static-threshold baseline.

Named after the multi-headed dog guarding the gates: a multi-tier guard sitting
at the kernel "gate" where packets enter.

## Start here

1. Read `docs/PROJECT_CONTEXT.md` — the source of truth: what this is, the
   architecture, tech stack, novelty, build order, and scope limits.
2. Follow `docs/SETUP_GUIDE.md` — environment setup (Ubuntu 24.04 + BCC toolchain).
3. See `docs/FOLDER_LAYOUT.md` — the target repo structure and how it maps to the
   build milestones.

## Stack (short version)

Tier-1 kernel program in eBPF C, loaded with **BCC** (Python bindings). Userspace
(collector, CLI, control loop) in **Python 3**. Tier-2 is a **scikit-learn
decision tree** trained offline on **CIC-IDS-2017**. Storage is **SQLite**;
dashboard is **HTML + Chart.js**; attack traffic via **hping3**. Chosen throughout
for simplicity over production robustness — this is a research prototype.

## Build order

Bottom-up, each milestone runnable before the next: M0 hello-eBPF → M1 count all →
M2 per-IP count + drop (Tier 1) → M3 collector/CLI/dashboard → M4 adaptive
threshold → M5 decision tree (Tier 2) → M6 evaluation. Details in
`docs/PROJECT_CONTEXT.md` §5.

## Why one repo

Cerberus is a single repo (monorepo), not one repo per service. The kernel
program, its loader, and the collector all read the same BPF maps and must change
together — one atomic commit keeps them consistent, and an examiner can clone one
repo to reproduce everything. Folders give clean per-component separation within
the repo. See `docs/PROJECT_CONTEXT.md` §9.

## Golden rules

- Build and test **milestone by milestone**; never dump large untested code.
- Protect the three novelty elements; keep everything else simple.
- Guard against **scope creep** — build the minimum system that produces the
  comparison the research question asks for.
