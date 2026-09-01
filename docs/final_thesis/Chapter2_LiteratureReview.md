# CHAPTER 2 - LITERATURE REVIEW

## 2.1 Chapter Overview

This chapter reviews the published literature relevant to kernel-level DDoS detection
with eBPF and XDP. The chapter is structured to build an argument rather than simply
list every paper in turn: it moves from the overall context of the domain, through a
comparative review of existing systems that includes the researcher's own judgement on
their suitability to the present problem, to a closer technological analysis of the
algorithms, designs, and workflows those systems use. It ends with a reflection that
draws the threads together and restates the research gap identified in Chapter One
against the literature that supports it.

## 2.2 Conceptual Map of the Literature

To help the reader navigate the chapter, the literature has been arranged into three
layers, summarised in Table 2.1. The first layer covers domain-level background: the
nature of DDoS attacks and the pre-eBPF mechanisms used to mitigate them. The second
layer covers current eBPF/XDP-based systems, grouped loosely by where they are deployed -
edge/IoT, cloud/data-centre, container/Kubernetes, and Software-Defined Networking. The
third layer sits apart from deployment context and instead looks at the algorithm,
architecture, and workflow choices these systems make. More weight is given to this third
layer in what follows, because it is at this level, rather than at the level of "which
environment was tested," that the research gap identified in Chapter One actually sits.

| Layer | Focus | Representative Sources |
|---|---|---|
| Domain background | DDoS taxonomy; pre-eBPF kernel filtering (netfilter/iptables, kernel-bypass approaches) | Abranches et al. (2021); StationX (2026) |
| Existing systems | eBPF/XDP DDoS systems by deployment context | Tolay (2025); IEEE (2025); MDPI (2023); Elzoghbi and He (2025) |
| Technological themes | Algorithms, architecture, and workflow patterns across systems | Anand et al. (2025); Hara and Sasabe (2024); Farasat et al. (2024); Zheng and Zhang (2026) |

*Table 2.1: Conceptual map of the literature*

## 2.3 Domain Overview

DDoS attacks generally fall into three types. The most common volumetric attack is a SYN
flood; the most common protocol attack is an amplification attack, such as a CLDAP
reflection; and the most common application-layer attack is a flood of well-formed
requests that is difficult to tell apart from legitimate load.

Before eBPF, packet filtering in the Linux kernel was mostly handled through netfilter
and its front-ends, iptables and nftables. These are flexible tools, but they were never
built for high-frequency, programmable, per-packet decision logic at line rate, and under
heavy traffic the cost of walking netfilter's rule chains becomes a real bottleneck. An
alternative approach, kernel-bypass frameworks such as Intel's DPDK, sidesteps the kernel
entirely and hands the network interface over to a userspace application, which gives
very high throughput but at the cost of the kernel's normal device drivers, security
boundaries, and ease of integration with the rest of the operating system. eBPF and XDP
sit in between these two extremes: packet processing stays inside the kernel, keeping its
safety and integration benefits, but the program attaches early enough in the receive
path to avoid much of netfilter's overhead. It is this middle ground that makes the
technology attractive for DDoS defence, and it is the foundation every system discussed
in the rest of this chapter builds on.

## 2.4 Existing Systems, Frameworks and Designs

This section summarises seven systems published between 2021 and 2026 that use eBPF/XDP
specifically for denial-of-service detection and mitigation, and evaluates each against
the problem this dissertation addresses.

Abranches et al. describe a network-monitoring system rather than a DDoS-specific one,
but it introduces an idea reused in almost every later DDoS-specific paper: combine
several monitoring tasks into a single eBPF program to avoid duplicating per-packet work,
and only run more expensive userspace analysis once a cheap in-kernel filter has flagged
something worth a closer look. This "filter cheaply, escalate selectively" idea is
closely relevant to the two-tier architecture proposed in Chapter One, and in this
researcher's view it is an idea that most of the subsequent DDoS-specific papers have not
picked up, since they mostly apply a single, generic detection mechanism uniformly to all
traffic.

Tolay presents a rate-based XDP mitigation approach aimed specifically at
resource-constrained IoT edge devices, tested against a 100 Mbps flood on a Raspberry Pi
4 and reporting over 97 percent mitigation effectiveness. This is well suited to its
stated environment, but it does not carry over neatly to the present research, because
the published evaluation does not include a legitimate traffic-surge scenario, and it
relies on a single, fixed-rate threshold, leaving the question of false positives
completely open. A cloud-data-centre paper published at IEEE applies a similar
rate-and-flow-tracking concept to east-west traffic inside cloud-native microservice
deployments, again reporting a meaningful reduction in communication overhead compared
with controller-polling approaches, but again without any flash-crowd evaluation. The
same family of techniques appears again, applied to pod-to-pod traffic filtering, in a
study published in MDPI Applied Sciences, which shows the approach works in both cloud
and container settings but makes no change to the underlying detection logic to address
adaptivity.

Moving to machine-learning-augmented systems, Anand et al. integrate eBPF with four
classic classifiers - Decision Tree, Random Forest, Support Vector Machine, and TwinSVM -
trained on the CIC-IDS-2017 dataset, with the Random Forest classifier reaching the
highest accuracy at 99.44 percent. This is a strong accuracy figure and is treated here
as a reasonable baseline for the offline-training side of the proposed prototype, though
integrating the classifier with XDP for lower-latency processing is left as future work
in the paper itself, and, like the systems above, the evaluation is carried out only
against labelled attack data. Hara and Sasabe take this a step further, showing that a
quantised integer-arithmetic neural network and a decision-tree classifier can both be
compiled to run within the constraints the eBPF/XDP verifier imposes, using BPF tail
calls to work around the instruction-count limit - a significant piece of
engineering in its own right, and one that speaks to the design choices made in this
dissertation's own prototype, discussed further in Section 1.8. The trade-off they
describe, however, is not something that can be changed at runtime; it is a design-time
choice between an in-kernel approach and an AF_XDP-offloaded userspace approach, not a
live decision the system makes for itself.

Farasat et al. combine a heavier BiLSTM threat-detection module with an eBPF/XDP
filtering layer in their SmartX Intelligent Sec framework, and report filtering over 2.2
million malicious packets in 15 seconds of live testing - the most operationally
convincing real-time demonstration among the papers reviewed here. Notably, the BiLSTM
model itself runs in userspace rather than inside the verifier, which the authors
themselves list as a limitation of the current work and mark out as future work rather
than presenting it as a settled design decision. This is judged here to be a reasonable
and honestly-reported engineering compromise, even though it reintroduces some of the
latency that XDP's earliest-possible-hook design is meant to remove, and it is a
compromise this dissertation's own prototype adopts for the same reasons. Zheng and Zhang
go further still, placing a convolutional neural network inside the kernel for edge
traffic classification, emphasising the ability to classify traffic at runtime without
duplicated effort, though at some cost to raw classification accuracy on constrained
hardware.

Finally, of the literature surveyed, Elzoghbi and He is the closest single piece of work
to the present research. They address the "frozen at deployment" weakness of the static
systems above by embedding an eBPF/XDP program into the data path of an OpenFlow switch
and recalculating detection thresholds dynamically to counter low-rate denial-of-service
attacks in a Software-Defined Network. What separates the present dissertation from being
a simple recreation of their work is two-fold: their adaptivity is statistical, meaning a
recomputed threshold rather than a learned model, and their architecture depends entirely
on an SDN controller and OpenFlow switches, neither of which forms part of the present
research - assuming otherwise would undermine the goal of a system deployable on an
ordinary Linux host.

## 2.5 Technological Analysis

### 2.5.1 Algorithmic Analysis

Two broad families of algorithm recur across the systems reviewed in Section 2.4. The
first, statistical or rate-based detection, computes simple aggregate features - packets
per second, bytes per second, SYN-to-ACK ratio - over a sliding or fixed time window, and
compares the result against a threshold stored in a BPF map keyed by source IP or flow
ID. This family is lightweight: a handful of arithmetic operations and a single map
access per packet, which is why it is the default choice in constrained settings such as
Tolay's IoT deployment, where the eBPF verifier's per-packet instruction budget is tight.
Its weakness, raised repeatedly in Section 2.4, is that a threshold on its own has no
concept of what counts as "normal" at a given time of day, or "normal" during a
promotional event, so any system relying on a threshold alone is structurally unable to
tell volume-driven legitimate traffic apart from a volume-driven attack.

The second family, learned classification, covers comparatively simple decision trees,
random forests, support vector machines, quantised neural networks, and convolutional or
recurrent architectures. This family is well known to be more accurate, but that accuracy
comes at a real cost inside the kernel: a decision tree compiles fairly easily into a
bounded sequence of branch comparisons, which is why it turns up in so many
"fits-inside-the-verifier" papers, whereas a neural network needs the quantisation and
tail-call workarounds that Hara and Sasabe had to engineer, precisely because the
verifier will not accept the floating-point arithmetic a conventional inference engine
would normally use. The implication for the proposed two-tier architecture is that its
escalation-tier classifier should be a small decision tree rather than a neural network -
not only because the verifier constraints favour it, but because that classifier is only
ever invoked on the minority of traffic already flagged as ambiguous by the cheaper first
tier, so the higher per-packet cost of a larger model is not needed in the first place.

### 2.5.2 Design Analysis

Architecturally, the systems reviewed differ along three dimensions. The first is
single-tier versus multi-tier processing: most of the reviewed systems apply one
mechanism, either a threshold or a classifier, uniformly to all traffic, with Abranches
et al., outside the DDoS-specific context, and to a lesser extent Farasat et al.,
splitting a cheaper always-on stage from a more expensive stage that is invoked
selectively. The second dimension is host-level versus controller-dependent deployment:
Elzoghbi and He's SDN/OpenFlow architecture trades the visibility a centralised
controller offers against the added complexity of deploying one, while the remaining
architectures, including the one proposed here, operate independently on a single host,
or, in the Kubernetes case, a single node. The third dimension, and the one most relevant
to this dissertation, is static versus adaptive parameterisation: every system reviewed
here hard-codes its thresholds and model weights at compile time, with the exception of
Elzoghbi and He, who recalculate a purely statistical threshold; none of them combine a
learned classifier with an update mechanism that runs in userspace and pushes changes
back through BPF maps. This third dimension is exactly where the research gap sits, and
it feeds straight into the userspace control-loop design described in Section 1.8.

## 2.6 Reflection

The literature reviewed here is concentrated mostly within the last two years, which
reflects how actively the eBPF/XDP subsystem is still developing - a paper from several
years earlier, even where the underlying idea has not aged badly, would likely be out of
step with what the current verifier actually allows. Reading across this recent
literature, the pattern flagged in Chapter One holds up under scrutiny: systems are
either fast and static, accurate but frozen once deployed, or adaptive only in a purely
statistical and controller-dependent sense. None of the sources reviewed combine a
learned, selectively-invoked classifier with a live, host-level, BPF-map-driven update
mechanism, and none of them measure false positives against a deliberately generated
traffic surge. This chapter therefore confirms, with the support of the literature
reviewed here, the research gap set out in Section 1.3.2, and the methodology proposed in
Chapter Three is aimed squarely at closing it.
</content>
