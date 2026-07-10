# Cerberus — project context

> Cerberus is a kernel-level, two-tier, online-adaptive DDoS detection and
> mitigation system. This document is the single source of truth for what the
> project is, why it exists, and how it is built. It is written so any Claude Code
> session (or collaborator) can read it once and understand the whole project
> without re-explaining. Read this before touching code.
>
> Name: Cerberus, after the multi-headed dog guarding the gates — fitting for a
> multi-tier guard that sits at the kernel "gate" where packets enter.

---

## 1. One-paragraph summary

This is a final-year BSc (Computer Networks) research dissertation project. It
builds a **two-tier, online-adaptive DDoS detection and mitigation system** that
runs partly inside the Linux kernel using **eBPF/XDP**. A cheap statistical
filter runs in the kernel on every packet (Tier 1). Only ambiguous traffic is
escalated to a small machine-learning decision tree in userspace (Tier 2). A
userspace control loop pushes updated detection thresholds down into the kernel
**live, via BPF maps, without ever reloading the kernel program**. The research
goal is to show this design keeps **false positives low against legitimate
"flash-crowd" traffic surges** while still detecting real DDoS attacks — and
that it beats a static-threshold baseline on that trade-off.

The author has near-zero prior programming experience, is working full-time on
this for roughly two months, and strongly prefers **simple and clear** solutions
over clever or complex ones. Every design choice favours "simplest thing that
produces a defensible research result" over production robustness. **Cerberus is
a research prototype, not a production product.**

---

## 2. The core research contribution (the novelty)

The novelty is **the combination of three things**, none of which is novel alone,
but which no single reviewed system combines:

1. **Adaptive, *learned* threshold updated without reload.** Simple tools use a
   fixed threshold (e.g. 250 packets/sec forever). The closest prior work
   (Elzoghbi & He) adapts, but only by recomputing a *statistical* threshold and
   only via an SDN controller. Nobody combines a *learned* model with live
   updates pushed into the kernel through BPF maps on a plain Linux host.

2. **Selective in-kernel ML escalation.** ML-based papers (e.g. Anand et al.)
   train classifiers offline and run them on all traffic or outside the kernel.
   Cerberus runs a cheap filter in-kernel on *everything*, and escalates only
   the small ambiguous slice to the ML tree. "Filter cheaply, escalate
   selectively," applied to DDoS specifically, is unexploited by the
   DDoS-specific literature.

3. **Flash-crowd false-positive evaluation.** Almost every tool/paper tests only
   against *attack* traffic and reports detection rate. Very few test whether they
   wrongly block a *legitimate* sudden surge (a flash crowd). Cerberus
   deliberately generates legitimate surge traffic and measures false positives
   against it. This is a **methodology** contribution and is the strongest,
   cleanest, most defensible novelty.

**When in doubt about scope, protect these three things and simplify everything
else.** The well-trodden parts (packet counting, dropping over a threshold) are
deliberately kept standard — reviewers do not reward reinventing them.

---

## 3. Where things live in Linux (mental model)

A packet's journey, bottom to top:

- **NIC (network card):** physical hardware. Packets arrive here first.
- **XDP hook:** the earliest software checkpoint, right as the packet leaves the
  NIC driver, *before* the normal kernel networking stack. This is where
  Cerberus's eBPF program runs and drops bad packets before any effort is wasted.
- **eBPF:** the technology that lets us safely run our own small program inside
  the kernel. A "verifier" checks the program can't crash or loop forever before
  it loads. The Tier-1 C program is an eBPF program attached at the XDP hook.
- **BPF map:** a small shared-memory area both the kernel eBPF program and
  userspace Python can read/write. It is the *only* bridge between the two
  worlds. Kernel writes packet counts in; userspace reads them out. Userspace
  writes a new threshold in; the kernel reads it on the next packet. This map is
  what makes live, reload-free threshold updates possible.
- **Userspace:** where ordinary programs run — Cerberus's Python collector, CLI,
  dashboard, control loop, and ML. A bug here crashes one program, not the machine.

**Critical performance fact:** the only performance-critical path (the "hot
path") is the eBPF program, which runs per-packet inside the kernel as verified
bytecode — the fastest place possible. Everything in userspace (the "cold path")
runs a few times per second, off the packet path, so **Python's slower speed is
irrelevant there.** This is the standard architecture for the whole field
(Cloudflare, SmartX, etc. all split it this way).

---

## 4. Tech stack (and why)

| Layer | Choice | Why |
|---|---|---|
| Tier-1 kernel program (hot path) | **eBPF in restricted C** | Unavoidable; only eBPF runs at the XDP hook. |
| eBPF loader / toolchain | **BCC (BPF Compiler Collection, Python bindings)** | Easiest to write and debug for a beginner; compiles on the machine, avoiding kernel-header mismatch errors; fastest edit-run-see loop. Chosen over libbpf/CO-RE and Go/cilium-ebpf deliberately — those are more robust for *production* but cost time this project doesn't have. |
| Userspace (cold path): collector, CLI, control loop | **Python 3** | Simple, standard, speed irrelevant off the packet path. |
| Tier-2 ML classifier | **scikit-learn decision tree**, trained offline | A decision tree compiles to a bounded sequence of comparisons — verifier-friendly and trivially fast to evaluate on the small ambiguous slice. NOT a neural network (verifier constraints; see §6). |
| Training dataset | **CIC-IDS-2017** | Already benchmarked in this project's literature review (Anand et al.). |
| Storage | **SQLite** | Simple, file-based, no server. Chosen over InfluxDB for simplicity. |
| Dashboard | **Plain HTML + Chart.js** | Simple, no build step. Chosen over React for simplicity. |
| Attack traffic generator | **hping3** | Standard tool for SYN floods etc. |
| Flash-crowd (legit surge) generator | **simple Python / standard load generator** | Produces the legitimate surge needed for the false-positive evaluation. |

**Environment:** bare-metal Ubuntu **24.04 LTS** (not the newest 26.04 — see
SETUP_GUIDE.md for the reasoning; in short, 24.04's eBPF toolchain is more
stable and better documented). Development is done in **Claude Code**.

---

## 5. Build order (milestones — build bottom-up, each must run before the next)

Each milestone produces something runnable and testable on its own. Never write a
large untested pile of code. The three novel blocks (M4–M6) sit at the top,
resting on a tested foundation.

- **M0 — Hello eBPF.** Smallest possible eBPF program that attaches at the XDP
  hook and lets packets pass. Proves the toolchain + machine can load eBPF at
  all. **Do this first, day one — it collapses most project risk.**
- **M1 — Count all packets.** One global counter in a BPF map going up; Python
  reads it. Proves kernel↔userspace via maps works.
- **M2 — Count per source IP + drop over threshold.** This is Tier 1, the real
  kernel heart. Parse the packet's source IP, count per IP in a hash map, return
  XDP_DROP over a threshold.
- **M3 — Userspace read layer.** Collector reads the map on a timer, writes events
  to SQLite; CLI (`ddosctl`) shows status/top/watch; HTML+Chart.js dashboard.
- **M4 — Adaptive threshold (NOVELTY b).** Userspace control loop writes an
  updated threshold into the BPF map live — no reload of the XDP program.
- **M5 — Decision tree, Tier 2 (NOVELTY a).** Train tree offline on CIC-IDS-2017;
  invoke it in userspace only on the ambiguous slice flagged by Tier 1.
- **M6 — Evaluation (NOVELTY c).** Fire attack traffic (hping3) and legitimate
  flash-crowd traffic; measure detection rate and false positives; compare the
  adaptive two-tier system against a static-threshold baseline. These numbers
  become the results/evaluation chapters.

---

## 6. Known real risks (name them, don't be surprised)

- **Setup friction is the biggest *time* risk**, not a capability risk. First-time
  eBPF loading can fail on kernel headers, NIC/XDP driver support, or permissions.
  M0 exists to hit these on day one. Fallback if the NIC lacks native XDP: **SKB /
  generic XDP mode** — slower, but fine for a research prototype measuring
  detection logic rather than raw throughput.
- **The eBPF verifier is a real constraint.** It rejects unbounded loops and
  programs over its instruction limit. This is *why* Tier 2 is a small decision
  tree, not a neural network. The unknown is the max tree depth the verifier
  accepts on this kernel — tunable (shrink the tree); it cannot kill the
  contribution because the research is about the *architecture*, not model size.
- **Measurement realism is the real intellectual challenge.** The flash-crowd
  scenario must be convincing enough that the static baseline actually produces
  measurable false positives to beat. Too gentle → no visible improvement. This
  deserves thought (and supervisor input), not last-week improvisation.

---

## 7. Scope discipline (the main failure mode)

The failure mode is **scope creep**, not technical impossibility. What is
realistic in two months is: *a working prototype that demonstrably shows the
adaptive two-tier design reduces flash-crowd false positives versus a static
baseline, on a single host.* That is a legitimate, defensible BSc contribution.

Do **not** chase: production hardening, multi-node deployment, maximum
throughput, every attack type, a large ML model. Each trades scarce time for
robustness the research does not need. Build the **minimum system that produces
the comparison the research question asks for.**

---

## 8. Working style / preferences

- Author prefers large, complete, well-explained deliverables over fragments, but
  **code must be built and tested milestone by milestone**, not dumped at once.
- Author works in two registers: formal academic prose (thesis) and plain-language
  conceptual explanation (kernel/eBPF/sequencing). Explain new concepts simply.
- Author has near-zero programming background — comment code generously and
  explain *why*, not just *what*.
- Consistent preference: **simple and clear, not complex.** This has already
  shaped tooling (SQLite over InfluxDB, HTML/JS over React, BCC over Go).

---

## 9. Repo structure decision (why one repo)

Cerberus is a **single repository (monorepo)**, not one repo per service. The
services are tightly coupled and change together: editing the BPF map layout in
`kernel/xdp_ddos.c` forces matching edits in `loader/ddos_loader.py` and
`backend/collector.py`, because they all read the same map. In one repo that is a
single atomic commit that stays consistent; split across repos it becomes several
commits that can drift out of sync. It also lets an examiner clone one repo and
reproduce the whole system. Folders (`kernel/`, `loader/`, `backend/`, `ml/`,
etc.) give clean per-component separation *within* the repo. See FOLDER_LAYOUT.md.

---

## 10. Academic framing (for thesis alignment)

- Thesis chapters 1–3 (Intro, Literature Review, Methodology, ~7,000 words, IEEE
  citations) already exist. Remaining: results, evaluation, conclusion — written
  from M6's real numbers.
- Eight competitor papers are benchmarked in the gap analysis (Anand et al. 2025;
  Farasat/SmartX 2024; Tolay 2025; Elzoghbi & He 2025/26; IEEE cloud-datacentre
  2025; MDPI Kubernetes 2023; Hara & Sasabe 2024; Zheng & Zhang 2026). AEGIS-BCO
  2026 and iKern 2024 are advanced adaptive systems used as contrast.
- Methodology is experimental: build the artefact, then run repeated experiments
  varying only the configuration, so observed differences are attributable to the
  configuration. Project management is agile/iterative (verifier behaviour can't
  be predicted up front).
