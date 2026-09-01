## Abstract

Distributed denial-of-service attacks continue to grow in both scale and frequency, and
defences that filter traffic inside the Linux kernel using eBPF and XDP have become an
attractive way to stop them at the earliest possible point in the network stack. These
kernel-resident filters are extremely fast, but the very constraints that make them safe
- a strict instruction-count limit, no unbounded loops, no floating-point arithmetic -
also make them coarse: most rely on a single, fixed packet-rate threshold, which cannot
tell a real attack apart from a legitimate flash crowd. Machine-learning classifiers
discriminate far better, but are usually applied to all traffic in userspace, which is too
slow to sit on the packet path, and the great majority of published work measures only
how well a system detects attacks, never how often it wrongly blocks legitimate users
during a surge.

This dissertation presents Cerberus, a two-tier, online-adaptive DDoS mitigation
prototype that addresses this gap head-on. A lightweight XDP program attached at the
network driver counts packets per source IP address and compares that count against a
threshold held in a BPF map, dropping or passing each packet with a single bounded
operation. Because the threshold lives in a shared map rather than being compiled into
the program, a userspace control loop can rewrite it at any time from recent traffic
statistics, and the very next packet is judged against the new value with no reload of
the kernel program. Sources whose counts fall within an ambiguous band are escalated
selectively to a decision-tree classifier trained offline on the CIC-IDS-2017 dataset,
keeping the more expensive classification step off the fast path entirely.

The prototype was implemented and evaluated on a live Ubuntu host. The classifier reached
an overall accuracy of 0.86 when trained and tested against 702,718 real, labelled
samples. In a controlled comparison, a static-threshold baseline and the adaptive
two-tier design both detected a volumetric attacker in full, but the static baseline
wrongly blocked all twelve simulated legitimate users during a flash-crowd scenario,
while the adaptive design blocked none of them. This result supports the central claim of
the dissertation: that a two-tier, adaptively-thresholded design can preserve attack
detection while substantially reducing the harm a DDoS defence causes to real users
during a legitimate traffic surge, addressing a dimension of the problem that existing
eBPF/XDP literature does not evaluate.
</content>
