# CHAPTER 1 - INTRODUCTION

## 1.1 Chapter Overview

This chapter sets out the research carried out on kernel-level DDoS detection using eBPF
and XDP. It gives the background that motivates the study, states the problem in general
and specific terms, and identifies the research question along with the motivation, aim,
and objectives that guide the rest of the work. It then states the three contributions
that together make up the novelty of this dissertation, before sketching the proposed
solution, listing the resources it needs, and marking out the boundary of what the
project does and does not attempt.

## 1.2 Problem Background - What Has Actually Happened?

Denial of Service attacks are not new, but they have grown sharply in scale, frequency,
and sophistication over the past two years. According to Cloudflare's threat intelligence
report, in 2025 they blocked 47.1 million DDoS attacks on their network, up from 22.1
million in 2024, and the first quarter of 2025 alone accounted for 96 percent of all DDoS
attacks blocked throughout the whole of 2024. A single attack, peaking at 31.4 terabits
per second and 14.1 billion packets per second, lasted just 35 seconds before being
automatically mitigated, as part of an internal campaign dubbed "The Night Before
Christmas" that occurred in December 2025. The botnet behind it, dubbed Aisuru-Kimwolf,
is believed to consist of anywhere from one to four million "smart" Internet of Things
devices, most of them Android-based TVs, and it can deliver simultaneous packet-rate and
bandwidth attacks across both TCP and UDP.

These numbers matter to this dissertation in two ways. First, the sheer volume of
present-day attacks makes it clear that detection at the application layer, or even
within the standard kernel network stack, is structurally unable to keep up - by the time
an attack reaches a userspace process, or even a fully-formed kernel socket buffer, the
system may already be overloaded. Second, the growing share of hyper-volumetric and
protocol-level floods, together with the persistence of application-layer floods that
mimic trusted users, makes a static rule unreliable: traffic from a popular promotional
campaign can look almost identical to traffic from a flood attack in one month, and quite
different from it the next. It is this second observation - the difficulty of telling a
real surge apart from a malicious one, and doing so within microseconds - that shapes
the specific research gap this chapter builds towards.

## 1.3 Problem Statement

Network operators today face a real dilemma. The sooner a bad packet can be dropped,
the less CPU time an attacker is able to steal from the system, because the packet never
reaches the layers of the operating system that would otherwise have to process it. The
eBPF/XDP subsystem of the Linux kernel is a strong answer to this half of the problem:
verified, sandboxed programs are attached at the network driver hook itself, so packets
can be classified and dropped before the kernel even allocates a full socket buffer
structure for them. At the same time, the very features that make eBPF/XDP safe and fast
- a small maximum instruction count, a limited per-program stack, and no unbounded loops
- make it hard to place any real intelligence inside that hook. Published systems tend to
fall into two camps as a result, and both camps share a shortcoming this dissertation
tries to correct.

### 1.3.1 General Problem

This paradox forces organisations to choose between speed and intelligence.
Static, threshold-based filters compiled into XDP - for example, dropping any source IP
whose packet rate crosses a fixed number - are cheap enough to run on every packet, but
cannot tell a real traffic surge (a flash sale, a viral post, a major sporting result)
from an attack, since both produce the same sudden spike against the same fixed number.
On the other hand, anything that needs the model itself to change, which in turn requires
an update to the eBPF program, is disruptive to carry out while the system is actively
defending live traffic; decision trees and quantised neural networks can be trained to
recognise far more nuanced attack patterns, but only offline, before the program is
loaded. Either way, the defence ends up acting too simply or too slowly for the pace of
real traffic and real attackers.

### 1.3.2 Specific Problem

At the level of this specific research domain, the shortfall can be stated more
precisely. Three trends recur across the recent eBPF/XDP DDoS literature. The mitigation
results reported for static, rate-based systems tested against synthetic flood traffic
such as hping3 look good against a flood, but none of the studies reviewed test the
detection logic against a burst of traffic that is deliberately legitimate, so the chance
that a real user gets blocked is never actually measured. Some machine-learning systems
compiled around eBPF - decision-tree and quantised neural-network classifiers among them
- report strong accuracy figures, mostly above 95 percent, but these figures come from
labelled attack datasets such as CIC-IDS-2017 and CICDDoS2019, and the models that are
actually deployed stay static once trained. The single closest piece of work, a 2025
framework that builds adaptive, dynamically-thresholded detection logic straight into
OpenFlow switches, does solve the adaptivity problem, but only by recalculating a
statistical threshold rather than adjusting a learned model, and it depends
architecturally on an SDN controller, which limits how it could be used in a host-level,
controller-independent deployment.

Looked at one at a time, the studies above each cover at most one of these three ideas,
and even then only in part. Abranches et al. show that a cheap in-kernel filter can hand
the harder work to a more expensive check, but they do this for general network
monitoring, not for DDoS detection. None of the DDoS-specific systems reviewed - Anand et
al., Hara and Sasabe, Farasat et al., or Zheng and Zhang - pick that idea up; each runs
its classifier over all traffic rather than saving it for the sources the first tier
cannot already sort out. On the second idea, adaptivity, Elzoghbi and He come closest,
because they recalculate their threshold while the system runs. But that threshold is a
statistical recalculation, not the escalation boundary of a learned model, and their
design needs an SDN controller and OpenFlow switches instead of a plain Linux host. Hara
and Sasabe, for their part, describe a choice made at design time between running the
classifier in the kernel or in userspace, not a decision the system makes for itself
while it is running. The third idea, the evaluation method, is where the gap is clearest.
Tolay openly leaves the question of false positives unanswered, the cloud and container
systems report no flash-crowd test at all, and even the highest accuracy figures in the
reviewed papers - Anand et al.'s 99.44 percent, Farasat et al.'s filtering of 2.2 million
packets in live testing - come only from labelled attack data, never from a legitimate
surge generated on purpose. So parts of the problem have been solved on their own, but no
single paper reviewed here puts all three together: a two-tier pipeline that escalates
only ambiguous traffic, a threshold that can be changed at runtime without reloading the
XDP program, and an evaluation that measures false positives against a legitimate flash
crowd rather than against attack traffic alone. That combination is what this dissertation
sets out to build and test.

## 1.4 Research Question

How can a kernel-level eBPF/XDP DDoS detection system dynamically adjust its detection
threshold without reloading the running program, while preserving the accuracy of attack
detection and significantly lowering false positives when legitimate network traffic
suddenly increases?

This primary question is answered in several ways across the dissertation, and it splits
into two sub-questions: what architecture is needed to let a userspace control process
safely and efficiently update kernel-resident detection parameters without simply moving
the problem back up into userspace, and what evaluation methodology is needed to show,
with evidence, that adaptivity actually changes the trade-off between attack detection
and false-positive rate, rather than just shifting where that trade-off is made.

## 1.5 Research Motivation

This research is not only practical, it is personal as well. From a practical point of
view, the statistics cited in Section 1.2 make it clear that DDoS has stopped being an
occasional event and has become, in the words of Zayo's 2026 Cybersecurity Insights
Report, "a permanent and highly disruptive reality for all organisations." Akamai and
Cloudflare are enterprise-grade scrubbing providers, but small and medium-sized
organisations face the same hyper-volumetric and adaptive attacks that large
organisations are working to combat, usually without the budget for that kind of
protection. A lightweight, self-tuning, host-level defence that can be deployed on an
ordinary Linux server, without needing a Software-Defined Networking controller or a
dedicated scrubbing centre, therefore has direct practical value.

On a more personal level, the appeal of the topic lay in the chance to work at the actual
interface between operating-systems research and applied security. What started as a
fairly broad idea - "DDoS detection using eBPF/XDP" - and the wish to work inside the
Linux kernel while engaging with a live and growing security problem, is what narrowed
down into the specific research gap identified above.

## 1.6 Research Aim

This work aims to design, implement, and empirically assess a two-tier, online-adaptive
DDoS detection and mitigation solution built on eBPF/XDP, one that suppresses false
positives on legitimate flash-crowd traffic while maintaining detection accuracy against
representative DDoS attack traffic, and to show through empirical evaluation that this
solution outperforms existing static-threshold baselines.

## 1.7 Research Objective

### 1.7.1 To identify

To identify the limitations of existing eBPF/XDP approaches to DDoS detection, and among
these, the issues around adaptivity and the way these systems are tested against
legitimate traffic surges.

### 1.7.2 To analyse

To compare a statistical threshold approach against a compiled machine-learning approach
under the constraints imposed by the eBPF verifier, in order to design a hybrid two-tier
architecture.

### 1.7.3 To design and develop

To build a working prototype that combines a lightweight machine-learning classifier,
invoked selectively rather than on every packet, with a low-cost, kernel-resident
statistical pre-filter at the XDP hook, together with a userspace control-loop daemon
that can change the detection threshold via a BPF map without reloading the XDP program.

### 1.7.4 To evaluate

To experimentally test the prototype against both synthetic DDoS attack traffic and
deliberately generated legitimate flash-crowd traffic, measuring detection accuracy,
false-positive rate, throughput, and CPU overhead, and to compare the results against a
static-threshold baseline.

## 1.8 Research Contributions and Novelty

As Section 1.3.2 explained, the gap is not that any single one of these ideas is missing
from the literature. It is that no system brings all three together. This dissertation
makes three contributions, and its novelty is in combining them in one system that runs
on an ordinary Linux host.

**Contribution 1 - An adaptive detection threshold that is updated live, without
reloading the XDP program.** A userspace control loop keeps track of the recent traffic
rate and writes an updated threshold into a shared BPF map. The kernel program reads that
value on the next packet it handles. Because the threshold sits in a map instead of being
compiled into the program, it can be changed while the system is still running and still
filtering traffic, with no recompilation and no reload of the XDP hook. This is the thing
the static systems in Chapter Two cannot do, since their threshold is fixed once the
program is loaded. The closest existing work, by Elzoghbi and He, does adjust its
threshold while running, but it needs an SDN controller and OpenFlow switches to do so;
the system here needs neither.

**Contribution 2 - A two-tier pipeline that escalates only ambiguous traffic to a
machine-learning classifier.** The cheap statistical filter at the XDP hook runs on every
packet. The decision-tree classifier does not. It is called only for the small group of
sources that the first tier cannot clearly label as either normal or hostile. This keeps
the heavier classification work off the per-packet path, and spends it only where it
might change the outcome. None of the DDoS-specific systems reviewed in Chapter Two use
their classifier this way; each one runs its model over all traffic instead.

**Contribution 3 - An evaluation that measures false positives against legitimate
flash-crowd traffic, not against attack traffic alone.** As well as generating synthetic
attack traffic, the evaluation generates a sudden burst of legitimate traffic - a flash
crowd - and counts how many real users the system wrongly blocks under a fixed threshold
compared with the adaptive one. This is the weakness that shows up most often in the
reviewed work, where even the systems with the highest reported accuracy are only ever
tested against labelled attack data. It is also the part of the evaluation that the main
claim of this dissertation depends on, and it is set out in full in Chapter Six.

The three contributions are not separate features bolted together. The selective two-tier
design (Contribution 2) is what makes it affordable to run a machine-learning tier on the
host at all. The live threshold (Contribution 1) is what lets that pipeline adjust itself
while it runs, instead of being tuned once and then left alone. The flash-crowd
evaluation (Contribution 3) is what shows the adaptivity actually improves the balance
between blocking attackers and letting real users through, rather than just moving the
problem somewhere else.

## 1.9 Rich Picture of the Proposed Solution

The proposed architecture can be thought of as two co-operating parts that sit either
side of the kernel/userspace boundary. The XDP program is attached to the network
interface driver and receives every packet before the kernel builds any further
structures for it. For each IPv4 packet, it performs one cheap, bounded operation: it
increments a per-source-IP counter held in a BPF hash map and compares that count against
a threshold held in a separate BPF array map, rather than one hard-coded into the
program. If the count has reached the threshold, the packet is dropped immediately with
XDP_DROP; otherwise it is passed on with XDP_PASS. This part of the design is
deliberately minimal - a lookup, an increment, and a comparison - so that it stays well
inside the instruction and complexity limits the eBPF verifier imposes.

The second part is a userspace daemon that manages the pipeline alongside the kernel. It
periodically reads the aggregate statistics out of the BPF maps, works out a new baseline
for "normal" traffic using an exponentially weighted moving average, and writes an
updated threshold back into the BPF map that the kernel program reads on the very next
packet. Because this value can be changed from userspace at any time without unloading
the program, the detection logic that applies at three in the morning, when traffic is
quiet, can be different from the logic in place during a lunchtime sale, and the
transition between the two happens automatically.

Sources whose counts sit in an ambiguous band - busy enough to be suspicious, but not yet
over the hard threshold - are escalated to a small decision-tree classifier. Unlike the
statistical pre-filter, this classifier is not compiled into the XDP program itself; it
runs in userspace and is invoked only for that ambiguous minority of sources, so the more
expensive classification step never sits on the packet path. This mirrors a design choice
also made by comparable published systems - the SmartX Intelligent Sec framework, for
example, keeps its BiLSTM-based classifier at the user level for the same reason,
describing the trade-off as a limitation to be revisited in future work rather than a
flaw that undermines the contribution. The classifier is trained offline, and its output
feeds back into the same userspace control loop that manages the threshold, so that a
consistently-suspicious source can influence how quickly the threshold reacts.

A separate evaluation harness, conceptually apart from the running defence but central to
the research contribution, replays both attack traffic - generated with hping3 - and
synthetic flash-crowd traffic that mimics a real burst of legitimate connections from
many distinct sources, and logs the resulting detection accuracy and false-positive
behaviour for each scenario.

{{FIGURE_1_1}}

## 1.10 Resource Requirements

### 1.10.1 Hardware

- A Linux host with kernel-level access, either a physical machine or a virtual machine,
running a kernel of at least version 5.10 so that the BPF map types and XDP hooks the
system depends on are stably supported. The prototype was developed and tested on a host
running kernel version 7.0.0.
- A source of test traffic. The project supplies its own generator scripts for this -
attack_gen.py for attack traffic and flashcrowd_gen.py for legitimate flash-crowd traffic
- so that no separate commercial tool is needed. Running these generators on a second
machine, kept separate from the host being defended, is the recommended setup where one is
available, so that the generator's own CPU load does not affect the measurements taken on
the host. The evaluation in Chapter Six was run on a single host, which is noted there as a
limitation of the test setup.
- Where available, a network interface card that supports native XDP mode rather than the
slower generic/SKB fallback, for more accurate throughput figures.

### 1.10.2 Software

- Headers and libraries for compiling and loading eBPF/XDP programs on the Linux kernel,
via the BCC toolchain.
- clang/LLVM for compiling C programs down to BPF bytecode, and bpftool for inspecting
loaded programs and BPF maps.
- A userspace control-loop daemon written in Python, using BCC's Python bindings, to read
and write BPF map values.
- The CIC-IDS-2017 dataset for offline model training and as a source of labelled attack
and benign traffic for evaluation.
- Traffic generation and replay tools, principally hping3 for attack traffic, together
with a purpose-built Python generator for legitimate flash-crowd traffic.
- Standard Python data-analysis tooling - pandas, scikit-learn, and matplotlib - for
offline model training and result analysis.

## 1.11 Project Scope

**In Scope**

- Detection and mitigation of representative volumetric and protocol-level DDoS patterns,
such as SYN floods and UDP floods, at the host level using eBPF/XDP.
- Design and implementation of a two-tier detection pipeline within the constraints of
the eBPF verifier, combining a statistical pre-filter with a selectively-invoked
machine-learning classifier.
- Experimental testing using synthetic attack traffic and synthetic legitimate
flash-crowd traffic, run on a host or a small testbed.

**Out of Scope**

- Mitigation of encrypted, low-rate, or fully application-layer (Layer 7) attacks that
closely mimic legitimate HTTP/HTTPS request semantics; this is left as future work.
- Distributed or multi-node coordination of detection state across a fleet of machines;
this dissertation addresses single-host adaptivity only.
- Integration with a Software-Defined Networking controller or OpenFlow switches; the
proposed system is intentionally host-level and controller-independent.
- Production-grade deployment, large-scale load testing beyond the available
infrastructure, or commercial packaging of the prototype.

## 1.12 Chapter Summary

This chapter placed the dissertation in the context of the rapid growth in the volume and
sophistication of DDoS attacks, and used that context to motivate a precise problem
statement: existing eBPF/XDP detection systems are either fast but static, or accurate
but frozen once deployed, and none of the reviewed literature tests how these systems
behave when faced with a legitimate traffic surge. A single research question, a
supporting aim, and four research-specific objectives were drawn from this problem
statement, and the three contributions that together make up the novelty of this work -
the live-updatable threshold, the selective two-tier pipeline, and the flash-crowd
false-positive evaluation - were stated explicitly, alongside a description of the
proposed two-tier, online-adaptive solution, the resources it requires, and a clear
boundary of what the project will and will not attempt. Chapter Two now turns to a
detailed review of the literature that this problem statement is built on.
