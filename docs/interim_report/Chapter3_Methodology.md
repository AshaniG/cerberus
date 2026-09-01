# CHAPTER 3 - METHODOLOGY

## 3.1 Research Paradigm

This research is conducted in a broadly post-positivist manner. The research question is
treated as one with an objective, repeatable, measurable answer - in this case, the
accuracy of detection, the false-positive rate, throughput, and CPU overhead, all
collected under controlled experimental conditions - while still recognising, as a strict
positivist stance would not, that the choice of which features to measure, which
thresholds to use, and which traffic scenarios to test is itself a design decision shaped
by the researcher's reading of the literature reviewed in Chapter Two. The claim this
dissertation sets out to support is one that should be backed by quantitative,
instrument-collected evidence rather than by interpretive methods such as interviews or
case-study narrative, because what is being studied is a measurable behaviour of a
system, not a subjective experience or a social meaning.

## 3.2 Research Approach

The research follows a deductive approach. The gap identified in the literature review in
Chapter Two is well defined and testable: existing systems cannot combine selective
machine-learning escalation, live threshold adaptation, and flash-crowd-aware evaluation
without measurably compromising attack-detection accuracy, and the proposed architecture
should be able to reduce the false-positive rate on flash-crowd traffic to a measurably
lower figure than existing static baselines while keeping detection accuracy at an
acceptable level. The remainder of the methodology is built to test this expectation
directly, rather than to build new theory inductively from open-ended observation. The
engineering decisions described in Chapter One - such as choosing a decision tree over a
neural network for the escalation tier, or keeping that classifier in userspace rather
than compiling it into the XDP program - are not driven by a single overriding research
philosophy so much as by what could realistically be built and verified within the
project's timeline, and by the hard limits the eBPF verifier imposes.

## 3.3 Research Strategy

The overall strategy is experimental and centres on a working software prototype. This
differs from a survey approach, which would rely on questionnaires or interviews, and
from a pure case-study approach, which would examine an existing deployed system rather
than build a new artefact. The plan instead is to construct the artefact described in
Chapter One and then run repeated experiments on it under varying conditions, using the
same test traffic, hardware, and measurement apparatus each time, changing only the
architectural configuration under test - so that any difference observed between runs can
be attributed to that configuration rather than to chance or to some uncontrolled
difference in the inputs.

## 3.4 Fact Collection Mechanisms

Two types of information are gathered. The first is literature-derived fact, drawn from
established databases and venues - ScienceDirect, IEEE Xplore, arXiv, Springer, and MDPI
- searched for publications on DDoS detection, with claims cross-checked against their
original source where possible, and each source's evaluation methodology documented in
order to identify the specific "flash-crowd evaluation gap" this dissertation targets.
The second is experiment-derived fact, gathered by instrumenting the prototype directly
during testing: packet counters and timestamps read from BPF maps, CPU utilisation
gathered from standard Linux tools such as perf and /proc/stat, and ground-truth labels -
attack or legitimate - attached to each generated packet by the traffic-generation
harness itself, so that detection outcomes can be scored automatically rather than judged
by hand.

## 3.5 Research Methodology Execution Workflow

| Workflow Stage | How It Was Addressed |
|---|---|
| 3.5.1 Problem Identification | Addressed through background research into current industry threat statistics (Section 1.2), cross-checked against the literature's own stated limitations (Section 2.4). |
| 3.5.2 Relevance Justification | Addressed through Cloudflare and industry threat-report statistics demonstrating the scale and urgency of the DDoS problem, and through the literature gap established in Section 2.6. |
| 3.5.3 Comparative Analysis and Gap Justification | Addressed through the seven-system comparative review in Section 2.4 and the cross-cutting technological analysis in Section 2.5, concluding in the explicit gap statement of Section 2.6. |
| 3.5.4 Define and Finalise Objectives | Addressed through the four research objectives in Section 1.7, each traceable to a specific element of the identified gap. |
| 3.5.5 Design, Development, and Data Management | Addressed through the two-tier architecture and userspace control-loop design in Section 1.8, implemented using the toolchain in Section 1.9, with experimental data version-controlled alongside the source-code repository for traceability. |
| 3.5.6 Evaluation and Communication | Addressed through the controlled experimental comparison described in Section 3.3, with results reported quantitatively against static baselines and communicated through the dissertation's results and discussion chapters. |

*Table 3.1: Research methodology execution workflow*

## 3.6 Project Management Methodology

The agile, iterative nature of the implementation work makes the eBPF verifier's exact
behaviour difficult to predict in advance when testing different feature sets or model
sizes, so an agile framework built around a visible backlog and short iterations was
judged more suitable than a stage-gated framework such as PRINCE2. PRINCE2 tends to
define requirements and deliverables in detail up front, which sits uncomfortably with
the genuine technical uncertainty in this project - for instance, whether a given
decision-tree depth will fit inside the verifier's instruction-count limit on the
available kernel version is not something that can be known until it is tried. A visible,
continually reprioritised task board handles that kind of uncertainty far better than a
formal stage review does. The dissertation deadline of two months was fixed from the
start, and the detailed ordering of tasks within that window was allowed to shift week to
week depending on what the implementation revealed.

### 3.6.1 Project Timeline

| Week | Task | Output |
|---|---|---|
| 1 | Set up Linux VM and BCC/eBPF tools; write a basic XDP program with a fixed packet-rate threshold | A simple XDP program that drops or passes packets |
| 2 | Add per-source-IP counting and threshold-based dropping at the XDP hook | A working detection program (xdp_ddos.c) |
| 3 | Build a Python backend to read kernel data and persist it to a database | A working data collector, with a MongoDB Atlas store and a local SQLite fallback |
| 4 | Train a small decision-tree model offline on attack data; add it as a selectively-invoked second detection layer | A two-tier detection pipeline (rule-based plus ML) |
| 5 | Build a REST API (FastAPI) so backend data can be requested; add live threshold updates | A working API |
| 6 | Connect the frontend dashboard to the real API instead of test data | A live dashboard showing real attack data |
| 7 | Test the system against attack traffic and normal traffic; record accuracy and false positives | Test results and a comparison table |
| 8 | Write up results; prepare the final report and demo | Final dissertation chapters and demo |

*Table 3.2: Project timeline*

### 3.6.2 Ethical Considerations

Several ethical safeguards were built into this research, given that the attack traffic
involved was artificially generated and replayed in a DDoS-like manner. All attack
traffic was either generated live inside an isolated test network with no access to the
public internet, so that no third party could be affected, or drawn from labelled
datasets intended for this purpose. No real user data was collected or used at any point
in the evaluation, and all traffic treated as a "legitimate flash crowd" was synthetically
generated rather than captured from a real production system, so no personal-data or
privacy concern arises. The dataset used to train the offline classifier, CIC-IDS-2017,
is published, de-identified, and licensed for academic research use by the Canadian
Institute for Cybersecurity, and was used strictly within the terms of that licence.
Finally, because the resulting prototype is, by its nature, a description of how certain
classes of static DDoS defence can be evaded - chiefly, by staying just under a fixed
threshold - the contribution of the dissertation is deliberately framed around defensive
adaptivity rather than published as a step-by-step attack-evasion guide, in line with
responsible-disclosure practice in security research.

## 3.7 Chapter Summary

This chapter set out the post-positivist, deductive, and experimentally grounded
methodology used to address the research question posed in Chapter One, along with the
fact-collection process behind it. It showed, stage by stage, how each part of the
research workflow - from problem identification through to final evaluation - is
addressed by a specific part of the dissertation's design, and explained why an agile,
Kanban-style approach to project management was chosen over a more formal method such as
PRINCE2, given the genuine technical uncertainty of working inside the eBPF verifier's
constraints. The eight-week project schedule was set out, and the ethical considerations
around generating attack traffic and using a licensed dataset were discussed. The
detailed design of the prototype system follows in Chapter Four.

## References

1. Cloudflare, "DDoS Threat Report for 2025 Q1," Cloudflare Blog, 2025. [Online].
Available: https://blog.cloudflare.com/ddos-threat-report-for-2025-q1/

2. Swif, "DDoS Attack Statistics for 2026: Record Sizes, Hyper-Volumetric Attacks, and the
Botnets Behind Them," 2026. [Online]. Available:
https://www.swif.ai/blog/ddos-attack-statistics

3. M. Abranches, O. Michel, E. Keller, and S. Schmid, "Efficient Network Monitoring
Applications in the Kernel with eBPF and XDP," in Proc. 2021 IEEE Conf. Network Function
Virtualization and Software Defined Networks (NFV-SDN), 2021.

4. A. Tolay, "eBPF-Based Real-Time DDoS Mitigation for IoT Edge Devices,"
arXiv:2508.00851, 2025.

5. N. Anand et al., "Enhancing intrusion detection against denial of service and
distributed denial of service attacks: Leveraging extended Berkeley packet filter and
machine learning algorithms," IET Communications, vol. 19, e12879, 2025.

6. T. Hara and M. Sasabe, "Practicality of in-kernel/user-space packet processing
empowered by lightweight neural network and decision tree," Computer Networks, vol. 240,
2024.

7. M. Elzoghbi and H. He, "Kernel-Level LDoS Attack Detection in SDN Networks: An
eBPF/XDP Framework with Dynamic Thresholding," Computer Networks, 2025.

8. Telecom Ramblings, "DDoS Attacks Grow 70% Larger in 2025 as Enterprises Move into the
Crosshairs, Zayo Reports," 2026. [Online]. Available:
https://newswire.telecomramblings.com/2026/03/

9. StationX, "DDoS Statistics 2026: Attack Data, Records and Trends," 2026. [Online].
Available: https://app.stationx.net/articles/ddos-statistics

10. "Efficient DDoS Detection and Mitigation in Cloud Data Centers Using eBPF and XDP,"
IEEE Conference Publication, 2025.

11. "Detection of Denial of Service Attack in Cloud Based Kubernetes Using eBPF," Applied
Sciences (MDPI), vol. 13, no. 8, p. 4700, 2023.

12. Y. Zheng and J. Zhang, "In-Kernel CNN Inference for Edge Devices: An eBPF-Based
Approach to Low-Latency and Resource-Efficient Processing," in Algorithms and
Architectures for Parallel Processing, ICA3PP 2025, LNCS vol. 16387, Springer, 2026.

13. T. Farasat, J. Kim, and J. Posegga, "SmartX Intelligent Sec: A Security Framework
Based on Machine Learning and eBPF/XDP," arXiv:2410.20244, 2024.
</content>
