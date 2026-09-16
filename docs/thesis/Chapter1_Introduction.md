# Chapter 1 — Introduction

> **How to use this draft.** Every paragraph is based on the system you actually built
> (Cerberus). Read each one, make sure you can explain it in your own words, and replace
> every **[INSERT REAL SOURCE / STAT]** marker with a genuine, verified reference before
> you submit. Do not submit any statistic or citation you have not personally checked.

## 1.1 Chapter Overview

This chapter introduces the research and explains why it was undertaken. It opens by
describing what has been happening with distributed denial-of-service (DDoS) attacks and
why, despite years of attention, they remain one of the most persistent threats to online
services. From that broad picture the chapter narrows towards a specific and often
overlooked weakness in the way current defences behave: their difficulty in telling a
genuine attack apart from a sudden but entirely legitimate surge of real users, a situation
usually described as a flash crowd. Having established the problem, the chapter presents a
focused problem statement supported by recent evidence, separates the general implications
of the problem from the specific shortcomings within the technical domain of this work, and
closes that discussion by naming the research gap to be filled. It then sets out a single
research question, the motivation that led to the study, the aim of the work, and a set of
research-specific objectives. A rich picture of the proposed solution is given so that the
reader can see how the parts of the system cooperate before any technical detail is
introduced, and this is followed by the hardware and software resources used, a clear
statement of what the project does and does not attempt, and a short summary linking the
chapter to the rest of the dissertation.

## 1.2 Problem Background — what has actually happened

Almost every service that individuals and organisations depend on today is reachable over
the Internet. Banking, government portals, online retail, streaming, healthcare booking,
and education all assume constant availability, and that assumption is exactly what makes
availability such an attractive target. A distributed denial-of-service attack does not
attempt to steal data or gain control of a machine; its single goal is to make a service
unavailable to the people who legitimately want to use it. It achieves this by consuming
some finite resource — network bandwidth, connection state, CPU cycles, or memory — faster
than the victim can replenish it, until genuine requests can no longer be served.

What makes these attacks so difficult to counter is their distributed nature. Rather than
originating from a single, easily blocked source, the traffic is spread across a large
number of compromised machines, often ordinary home devices and, increasingly, poorly
secured Internet-of-Things hardware that has been recruited into a botnet. Because the
requests come from many places at once and each individual packet may be perfectly
well-formed, the defender cannot simply look for malformed data or a single bad address.
The challenge is not recognising an obviously broken packet but recognising an abnormal
*pattern* assembled from otherwise ordinary traffic.

Over recent years the problem has grown rather than receded. Industry threat reports
describe a steady rise in both the frequency of attacks and the peak volumes they reach,
with record-setting volumetric floods now measured in terabits per second and short,
high-intensity bursts becoming more common **[INSERT REAL STAT — e.g., the most recent
Cloudflare DDoS Threat Report or NETSCOUT Threat Intelligence Report; quote the specific
figure and its year]**. Two developments in particular have worsened the situation. The
first is accessibility: attack tools and even rentable "booter" or "stresser" services have
made launching a sizeable attack cheap and technically undemanding, lowering the barrier to
entry dramatically. The second is architectural: many established defences operate at a
distance from the machine being protected — in a dedicated scrubbing appliance, at the
network edge, or through a software-defined-networking controller — and while such placement
can bring considerable analytical power to bear, it also introduces delay, because each
packet or flow must travel to the decision point and a verdict must travel back before any
action is taken. Against short bursts, that round trip can be the difference between
absorbing an attack and being overwhelmed by it.

Running alongside the attack problem is a second phenomenon that looks almost identical from
the outside but is entirely benign: the flash crowd. A flash crowd is a sudden, sharp rise
in traffic produced by real users rather than by an adversary. Familiar examples include the
moment concert tickets are released, the opening of a major online sale, a breaking news
story that drives readers to a publisher, or the deadline of a public examination portal. In
each case a very large number of genuine visitors arrive within a short window. To a defence
that reasons only about volume, this legitimate surge is indistinguishable from a volumetric
attack, and a defence tuned aggressively enough to stop attacks may therefore block precisely
the users the service most wants to welcome. This tension — between reacting quickly enough
to stop a real attack and restraining that reaction enough to spare a legitimate crowd — is
the core difficulty that motivates the present research.

## 1.3 Problem Statement

Modern DDoS defences are forced into a trade-off that they handle poorly, and the cost of
handling it badly falls squarely on legitimate users. Recent studies continue to report both
rising attack volumes and a shift towards shorter, sharper bursts that leave defenders very
little time to react **[INSERT RECENT CITATION — a peer-reviewed source within the last five
years]**. Two properties of any decision therefore matter simultaneously: how *quickly* it is
made, because a slow decision cannot protect against a fast burst; and how *accurately* it
distinguishes attack traffic from a legitimate surge, because an inaccurate decision harms the
very users the service exists to serve. Most existing approaches optimise one of these
properties at the expense of the other, and almost none are evaluated on the second at all.

### 1.3.1 General Problem

At the most general level, the problem is that a defence is expected to be both fast and
discriminating, yet these two demands pull in opposite directions. A defence placed at the
earliest and fastest point in the system can discard bad traffic before any effort is wasted
on it, but at that point only very cheap logic can run, and cheap logic — typically a simple
volume threshold — cannot tell an attack from a legitimate surge. A defence that reasons more
carefully, for instance by applying machine learning to rich traffic features, can make far
finer distinctions, but such reasoning is usually positioned later in the path and applied to
all traffic, which makes it too slow to protect the system in real time. The high-level
implication is uncomfortable: organisations are pushed towards one of two failure modes.
Either they under-protect, accepting the risk of outages and the reputational and financial
damage that accompany them, or they over-block, turning away paying customers and legitimate
users during exactly the high-demand moments a business most wants to capture. Both outcomes
carry a real cost, and the second is frequently invisible because it is rarely measured.

### 1.3.2 Specific Problem

Within the specific domain that this research occupies — kernel-level packet filtering using
the extended Berkeley Packet Filter (eBPF) and the eXpress Data Path (XDP) — the shortcoming
becomes concrete and technical. An eBPF program attached at the XDP hook runs as verified
bytecode at the earliest programmable point in the Linux networking path, immediately after
the network driver and before the conventional networking stack. This position is what gives
in-kernel filtering its remarkable speed, because a packet can be dropped before the kernel
invests any further processing in it. The same environment, however, is deliberately
constrained: the eBPF verifier statically checks every program before it is allowed to load
and rejects anything containing unbounded loops or exceeding its instruction limits, precisely
so that a faulty program cannot destabilise the kernel. The practical consequence is that only
cheap, bounded computation is permitted on this fast path.

Because of that constraint, published XDP-based DDoS filters rely on coarse, volume-oriented
rules, most commonly a per-source packet-rate or packet-count threshold. Such a rule is fast
and predictable, but it carries no information about the intent behind the traffic. A threshold
set low enough to stop an attack will therefore also drop a legitimate flash crowd, while a
threshold set high enough to admit a flash crowd will let a moderate attack through. Machine
learning offers the discrimination that the threshold lacks, but the prevailing designs train a
model offline and then apply it to *all* traffic in userspace or in a separate system, which is
accurate yet far too heavy to sit on the line-rate packet path. Compounding both of these
issues, the great majority of published evaluations report only how effectively a defence
detects attacks and remain silent on how often it wrongly blocks legitimate traffic, so the
false-positive cost of a defence during a genuine surge is seldom quantified at all.

**Research gap.** Bringing these observations together, there is at present no in-kernel,
line-rate DDoS mitigation approach that selectively applies machine learning so as to remain
efficient *and* is explicitly designed and evaluated to minimise false positives against
legitimate flash-crowd traffic. Closing that gap is the focus of this research.

## 1.4 Research Question

The study is organised around a single question:

**Can a two-tier, kernel-level DDoS mitigation system — combining a cheap in-kernel filter
with selective machine-learning escalation and an adaptively updated threshold — reduce false
positives against a legitimate flash crowd while maintaining attack detection, compared with a
static-threshold baseline?**

Three sub-questions refine this main question and structure the investigation:

- Which cheap, per-source signals can be computed within the constraints of the eBPF verifier
  and still help to separate a legitimate surge from an attack?
- What proportion of traffic can be resolved by the in-kernel filter alone, so that only a
  small, genuinely ambiguous minority need be escalated to the machine-learning tier?
- How does an adaptively updated threshold behave during a legitimate surge compared with a
  fixed threshold, and does that behaviour translate into fewer wrongly blocked users?

## 1.5 Research Motivation

The motivation for this research is both practical and personal. The practical motivation
follows directly from the problem statement: the flash-crowd false-positive problem represents
a real and under-examined cost. A defence that blocks genuine customers during the busiest and
most valuable moments — a product launch, a ticket release, a seasonal sale — inflicts direct
harm even as it appears to "succeed" at stopping an attack, and yet the field has devoted the
overwhelming share of its attention to catching attacks and comparatively little to measuring
this harm. That imbalance leaves a meaningful, well-defined, and defensible space for a focused
contribution. The personal motivation is that the project offered an opportunity to work
directly with eBPF and XDP, a modern and increasingly important kernel technology used in
production by major infrastructure providers, and to do so by building and measuring a complete
system rather than by studying the problem only in the abstract. Committing to a working
artefact, rather than a purely theoretical proposal, also imposed a healthy discipline: every
claim in the evaluation had to be backed by something the system actually did.

## 1.6 Research Aim

The aim of this research is to design, implement, and evaluate a two-tier, online-adaptive DDoS
mitigation system that operates partly inside the Linux kernel, and to demonstrate that this
design maintains attack detection while reducing false positives against legitimate flash-crowd
traffic relative to a static-threshold baseline. In short, the work seeks to show that a
defence can be made fast enough to act on the packet path and discriminating enough to spare a
legitimate surge at the same time, by dividing the labour between a cheap kernel filter and a
selective, more intelligent userspace tier.

## 1.7 Research Objectives

The following objectives are specific to this research rather than generic learning outcomes,
and each maps onto a part of the study.

1.7.1 **To identify** the constraints imposed by the eBPF/XDP environment, the specific
per-source signals that can be computed cheaply within those constraints, and the concrete
shortcomings of existing DDoS defences with respect to flash-crowd false positives.

1.7.2 **To analyse** how legitimate flash-crowd traffic and volumetric attack traffic differ in
ways that a two-tier design can exploit, and to analyse the trade-off between detection and
false positives that arises under different threshold strategies.

1.7.3 **To design and implement** Cerberus: a Tier-1 in-kernel XDP filter that counts per-source
traffic and drops over a live threshold; a Tier-2 userspace decision tree that classifies only
the ambiguous minority of sources; and an online control loop that updates the kernel threshold
through BPF maps without reloading the program.

1.7.4 **To evaluate** the system by generating both attack traffic and legitimate flash-crowd
traffic and by measuring attack detection and flash-crowd false positives for the adaptive
two-tier design against a static-threshold baseline, so that the research question can be
answered with evidence rather than assertion.

## 1.8 Rich Picture of the Proposed Solution

The proposed solution, Cerberus, is organised as two cooperating tiers that meet at a region of
shared memory. When a packet arrives at the network interface it first reaches the XDP hook,
where the Tier-1 program runs. Tier-1 performs only inexpensive work: it reads the source
address, updates a per-source counter held in a BPF hash map, compares that count against a
threshold stored in a BPF array map, and returns a verdict of either drop or pass. Because the
threshold lives in a map rather than being compiled into the program, userspace can change it at
any moment, and the very next packet will be judged against the new value with no reload of the
kernel program. This single property is what makes live, reload-free adaptation possible and is
central to the whole design.

Away from the packet path, and running only a few times per second, a userspace collector reads
these maps and records what it finds. Sources whose counts fall within an *ambiguous* band —
busy enough to be suspicious but not clearly attacking — are escalated to the Tier-2 decision
tree, which was trained offline on a labelled dataset and labels each such source as attack or
benign. In parallel, an online control loop observes the recent traffic rate and, when adaptive
mode is enabled, writes an updated threshold back into the kernel map so that the limit rises to
accommodate a genuine surge instead of blocking it. A lightweight dashboard reads the same
recorded state through a REST API and presents it to a human operator, and, for evaluation, a
pair of generators produce controlled attack and flash-crowd traffic. The essential idea to
carry forward is that the kernel and userspace remain two separate worlds joined only by the BPF
maps: counts flow upward from kernel to userspace, and an updated threshold flows back downward.

> *(Insert Figure 1.1 — the rich-picture / workflow diagram. A ready-made version of this
> diagram is available in `docs/HOW_IT_ALL_CONNECTS.md`; redraw it cleanly for the thesis.)*

## 1.9 Resource Requirements

### 1.9.1 Hardware
- A bare-metal host running Linux, used for both development and evaluation; the work was carried
  out on an x86-64 machine. A wired network interface is preferred because it is more likely to
  support native XDP, with generic (SKB-mode) XDP available as a fallback where native support is
  absent.
- For a stronger, multi-source evaluation, one or more additional machines or virtual machines to
  act as genuinely distinct traffic sources, since a single host cannot by itself represent the
  many separate users that characterise a real flash crowd.

### 1.9.2 Software
- **Ubuntu 24.04 LTS** as the operating system, chosen for a stable and well-documented eBPF
  toolchain rather than for the newest available release.
- **BCC (the BPF Compiler Collection)** to compile and load the Tier-1 C program, because it
  compiles the program on the host at load time and so avoids the kernel-header mismatch problems
  that can frustrate a first eBPF project.
- **Python 3** for the userspace services — the collector, the control loop, the REST API, and the
  command-line tool — where clarity matters more than raw speed because these run off the packet
  path.
- **scikit-learn** for the Tier-2 decision tree, with **pandas** and **NumPy** for loading and
  projecting the data, trained on the **CIC-IDS-2017** dataset.
- **FastAPI** together with **HTML, CSS, JavaScript and Chart.js** for the dashboard, and
  **SQLite** for local storage, keeping the stack reproducible and free of a heavy build step.
- **hping3** and a custom Python generator to produce the attack and flash-crowd traffic used in
  the evaluation.

## 1.10 Project Scope

| In scope | Out of scope |
|---|---|
| A single-host, two-tier prototype combining a Tier-1 XDP filter with a Tier-2 decision tree. | Multi-node or distributed deployment across a datacentre. |
| Live, reload-free threshold updates through BPF maps. | Production hardening, high availability, and long-term unattended operation. |
| Selective machine-learning escalation of only the ambiguous slice of traffic. | Deep neural networks or large models, which the verifier and the project scope both exclude. |
| A reproducible evaluation of attack detection *and* flash-crowd false positives against a static baseline. | Coverage of every DDoS attack class; the focus is volumetric flooding versus legitimate surges. |
| IPv4 traffic on a single network interface. | IPv6, application-layer (Layer-7) attack semantics, and inspection of encrypted payloads. |

The scope is deliberately narrow, and that narrowness is itself a design decision rather than an
oversight. The intention throughout was to build the minimum complete system capable of answering
the research question convincingly, rather than a broad or production-grade product. This focus
follows directly from the question, which concerns a specific trade-off — detection against
flash-crowd false positives — and not maximum throughput, exhaustive attack coverage, or
operational robustness. Keeping the boundary tight also made the work achievable within the time
available and kept the evaluation clean, because fewer moving parts meant that any measured
difference could be attributed to the configuration under test rather than to incidental
complexity.

## 1.11 Chapter Summary

This chapter established the setting for the research. It described how DDoS attacks have grown in
scale and frequency and why defences face a hard trade-off between acting quickly and acting
accurately, and it identified a specific and under-examined weakness at the heart of that
trade-off: existing in-kernel filters cannot separate a legitimate flash crowd from an attack,
and the great majority of evaluations never measure the harm done to legitimate users. From this
the research gap, the research question, the aim, and four research-specific objectives were
derived, and the two-tier adaptive design, Cerberus, was introduced together with the resources
it requires and the scope within which it was built. The next chapter reviews the relevant
literature in detail, positions the proposed approach against existing systems, and justifies the
research gap through a critical assessment of recent work.
</content>
