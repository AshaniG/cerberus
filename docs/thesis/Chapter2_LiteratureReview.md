# Chapter 2 — Literature Review

> **How to use this draft.** The domain overview and technological analysis below are written from
> general, correct knowledge of the field, but the *specific* comparisons in section 2.4 must be
> filled in from the papers you actually read. Wherever you see **[cite: … — verify]**, insert the
> full, real reference and check that the one-line summary matches what the paper really says. Do not
> attribute a claim to a paper you have not read. Most sources should be from within the last five
> years.

## 2.1 Chapter Overview

This chapter reviews the research and engineering work that surrounds the problem set out in Chapter 1.
Rather than listing sources one after another, the review is organised by the *approach* each source
takes, so that the strengths and weaknesses of a whole family of solutions can be weighed together and
so that my own position can be developed against them rather than merely alongside them. The chapter
first gives a conceptual map of how the literature is arranged, then a brief overview of the domain,
then a comparative assessment of the main families of existing DDoS defences. It then analyses those
approaches more closely at three levels — algorithm, design, and workflow — before drawing everything
together in a reflection that connects the reviewed work back to the gap this research addresses.
Throughout, the intention is to review critically rather than descriptively: where a design has a
weakness relevant to my research question, that weakness is named and its consequence drawn out.

## 2.2 Conceptual Map of the Literature

To keep the review coherent, the sources were arranged along two dimensions that matter most to the
research question. The first is *where* the defence runs, which ranges from far-off scrubbing
appliances and software-defined-networking controllers, through userspace daemons on the host, down
to programs executing inside the kernel itself. The second is *how* the defence decides, which ranges
from fixed rules, through statistical adaptation, to machine learning. A third question cuts across
both of these and is, for this work, the decisive one: does the source actually measure false
positives against legitimate traffic, or does it report only detection? Placing each reviewed work on
this map makes visible not only where it sits but, more usefully, which corner of the map is sparsely
populated. The sections that follow move through the map in order, beginning with the general domain,
proceeding to specific systems, and then examining the technology in closer detail.

> *(Insert Figure 2.1 — a conceptual map of the literature, with placement on one axis and decision
> method on the other, and the flash-crowd-evaluation question marked against each work reviewed.)*

## 2.3 Domain Overview

A distributed denial-of-service attack aims to exhaust a target's resources rather than to breach its
confidentiality or integrity. The family is usually divided into three broad categories. *Volumetric*
attacks, which are the focus of this research, simply overwhelm the victim's bandwidth or processing
capacity with sheer quantity of traffic. *Protocol* attacks exploit weaknesses in the way network
protocols manage state, for instance by exhausting a server's table of half-open connections.
*Application-layer* attacks target the logic of a specific service with requests that are individually
plausible but collectively ruinous. Across all three, the distributed origin of the traffic is what
makes the problem hard: because the load is assembled from many separate sources, often compromised
consumer and Internet-of-Things devices marshalled into a botnet, there is no single address to block
and each packet may be perfectly valid in isolation. The task facing a defender is therefore the
recognition of an abnormal aggregate pattern, not the recognition of an individually malformed packet.

Where a defence sits in the network path is as consequential as how cleverly it reasons. In the Linux
networking stack a packet passes first through the network driver and then through a long sequence of
processing stages before any application receives it. The eXpress Data Path, or XDP, is the earliest
programmable point in that sequence, situated immediately after the driver. A small program attached at
the XDP hook, expressed in the extended Berkeley Packet Filter (eBPF) instruction set, can inspect and
drop a packet before the kernel expends any further effort on it, which is the source of in-kernel
filtering's speed advantage. That advantage comes at a price. Before an eBPF program is permitted to
load, the kernel's verifier statically analyses it and rejects any program containing unbounded loops
or exceeding strict size limits, precisely so that a faulty or malicious program cannot compromise the
kernel's stability. The practical effect is that only cheap, provably bounded computation may run on
this fast path, which sharply limits how sophisticated an in-kernel decision can be and is the root
technical reason that richer reasoning must be delegated elsewhere.

The third element of the domain, and the one most central to this research, is the flash crowd. A flash
crowd is a sudden, steep rise in traffic produced not by an adversary but by a large number of genuine
users arriving within a short window — the release of concert tickets, the opening of a sale, a news
event, or an examination deadline. Although its cause is entirely benign, a flash crowd shares the one
feature that a volume-based defence keys upon, namely a sharp increase in traffic, and it is therefore
easily mistaken for a volumetric attack. The literature on flash crowds establishes both that the
phenomenon is real and economically important and that distinguishing it from an attack is genuinely
difficult **[cite: a recent flash-crowd study — verify]**, which frames the specific problem this work
attacks: not merely to detect attacks, but to detect them without mistaking a legitimate surge for one.

## 2.4 Existing Systems, Frameworks, and Designs

The systems reviewed fall into a handful of families, and it is more instructive to weigh each family
than to examine each paper in isolation, because the members of a family tend to share both a
characteristic strength and a characteristic limitation.

*Fixed-threshold and signature-based filters* are the oldest and simplest family. They drop traffic
that either matches a known signature or exceeds a static per-source rate. Their appeal is speed and
predictability, and because their logic is so cheap they map naturally onto in-kernel implementations.
Their defining weakness is rigidity. A threshold that is correct for a quiet period is wrong during a
surge, and there is no mechanism within the approach to tell the difference, so a threshold aggressive
enough to stop an attack is exactly the threshold that will block a legitimate flash crowd. In my
assessment this family defines the problem the present research responds to rather than solving it.

*Statistically adaptive defences* improve on the fixed threshold by recomputing the limit from recent
traffic. The closest example I reviewed adapts the threshold continuously, but it does so with a purely
statistical rule and drives that rule from a software-defined-networking controller rather than from
inside the host **[cite: Elzoghbi & He — verify]**. The advance here is real: an adaptive threshold is
plainly better suited to a fluctuating world than a fixed one. Yet two limitations remain relevant to
my work. First, relying on an external controller reintroduces the very round-trip delay that in-kernel
filtering exists to remove. Second, a statistical rule, however well tuned, still has no learned notion
of whether a given surge is legitimate; it adapts to volume, not to intent.

*Machine-learning detectors* bring the discrimination that thresholds lack. Trained offline on labelled
datasets such as CIC-IDS-2017, they can separate attack from benign traffic with high reported accuracy
**[cite: Anand et al. — verify]**. The limitation common to most of this family is one of placement and
scope rather than of accuracy: the classifier is typically applied to all traffic and runs in userspace
or offline, which is accurate but far too heavy to sit on the line-rate packet path. The lesson I drew
from this family is not that machine learning is unsuitable, but that it must be applied selectively
rather than universally if it is to coexist with line-rate filtering.

*In-kernel and eBPF/XDP systems* push filtering to the fastest available point and have been used
successfully for volumetric mitigation in both research and production **[cite: SmartX / Farasat —
verify]**. They confirm empirically that the hot path can be made extremely fast. However, the
published designs generally keep their in-kernel logic simple and coarse — as the verifier obliges them
to — and in doing so they inherit the flash-crowd blindness of the fixed-threshold family. They
demonstrate the speed half of the problem's solution without addressing the discrimination half.

*Flash-crowd-focused work*, finally, studies the similarity between legitimate surges and attacks
directly **[cite: Hara & Sasabe — verify]**. This family is encouraging because it shows the problem is
recognised and taken seriously, but the works I found tend to analyse or simulate the phenomenon rather
than to build a fast, in-kernel defence that is then evaluated against it. They supply motivation and
method for the false-positive question without supplying the in-kernel system that answers it.

The comparison below summarises how each family stands on the dimensions that matter to this research.
*(Complete the citation entries with your real, verified references, and expand each row with a
sentence or two of your own critical reflection drawn from the specific paper.)*

| Family (representative work) | Placement | Decision method | Adapts live? | Evaluates flash-crowd FP? |
|---|---|---|---|---|
| Fixed-threshold / signature | in-kernel / edge | static rule | No | No |
| Statistically adaptive [cite — verify] | SDN controller | statistical threshold | Yes (external) | Rarely |
| ML-based detector [cite — verify] | userspace / offline | trained classifier on all traffic | No | Detection-focused |
| eBPF/XDP volumetric filter [cite — verify] | in-kernel | coarse volume rule | Limited | No |
| Flash-crowd study [cite — verify] | analysis / simulation | statistical | — | Studies FP, not in-kernel defence |
| **Cerberus (this work)** | **in-kernel + selective userspace ML** | **cheap filter + escalated tree + adaptive threshold** | **Yes (via BPF map)** | **Yes — measured** |

## 2.5 Technological Analysis

### 2.5.1 Algorithmic Analysis

At the algorithmic level, the reviewed approaches occupy a spectrum that trades cost against
discrimination. At the cheap end, counting packets per source and comparing against a threshold is
extremely inexpensive and can be evaluated for every packet, but it carries no information about intent
and so cannot separate a surge from an attack. A step along the spectrum, statistical adaptation — for
example an exponentially weighted moving average of the traffic rate — adds a sense of what is "normal"
for the current moment at very little additional cost, which is precisely why the control loop in this
project adopts that idea to move the threshold rather than a more elaborate estimator. Further along,
a decision tree occupies a valuable middle ground: once it has been trained, evaluating it amounts to a
short, fixed sequence of comparisons, which is both fast and, crucially, bounded. That boundedness is
not an incidental convenience but a hard requirement near the kernel, because the eBPF verifier will not
admit unbounded computation. At the far, expensive end, deep neural networks offer the greatest
discriminative power but require unbounded or very large computation and substantial model state, which
places them firmly outside what can run on the fast path. This spectrum is the concrete reason that the
field, and this project, favour a shallow decision tree for anything close to the kernel: the intended
contribution lies in the architecture that decides *when* to invoke the model, not in the raw power of
the model itself, and a tree is both sufficient and affordable for the selective role it is given.

### 2.5.2 Design Analysis

The design question that recurs throughout the literature is placement, and each choice of placement
carries a characteristic trade-off. Defences positioned far from the host — scrubbing appliances,
network-edge devices, or SDN controllers — can bring considerable analytical power and a global view to
bear, but they add a round trip to every decision, which is costly against short, sharp bursts.
Defences positioned in userspace on the host are flexible and easy to develop, but they sit behind the
full networking stack and so cannot act before the kernel has already invested effort in a packet.
Defences positioned in the kernel act at the earliest and fastest point but are tightly constrained in
what they may compute. Taking all three trade-offs seriously points towards a single design: keep a
cheap, always-on filter on the hot path in the kernel, and reserve the expensive, more intelligent
decision for a cold path in userspace that runs only occasionally and only on the traffic the fast path
could not resolve. This hot-path/cold-path separation is well established in high-performance
networking generally, and the contribution of this work is not to invent it but to apply it
specifically to the flash-crowd problem, using the shared map both as the channel that carries counts
upward and as the channel that carries an adapted threshold back down.

### 2.5.3 Workflow Analysis

Viewed as a workflow, most machine-learning defences share a common two-phase shape: an offline
training phase that produces a model from labelled data, and an online phase that applies that model to
live traffic. What differs between designs, and what matters most for this research, is the boundary
drawn within the online phase between its fast and slow parts, and the manner in which those parts
communicate. In many of the designs I reviewed, that communication is loose, or changing the system's
behaviour requires reconfiguring or reloading a component. The workflow adopted here tightens the
coupling deliberately: the kernel writes per-source counts into shared BPF maps, userspace reads those
counts and, when it judges it necessary, writes an updated threshold straight back into the same maps,
and the kernel honours the new value on its very next packet without being reloaded. Treating the map
as the live contract between the two tiers is what allows selective escalation and reload-free
adaptation to coexist within a single, coherent workflow, and it is this workflow, more than any
individual algorithm, that distinguishes the proposed system from the designs reviewed here.

## 2.6 Reflection

Drawing the review together, three observations stand out, and they are not independent of one another.
First, adapting the detection threshold is known to help, but the existing adaptive schemes are either
purely statistical or depend on an external controller, and none of them combine a *learned* signal
with live, in-kernel updates. Second, machine learning clearly improves discrimination, yet it is
almost always applied to all traffic rather than selectively to the ambiguous minority, which is exactly
what keeps it off the fast path and confines it to userspace or offline use. Third, and most tellingly,
the overwhelming majority of the work reviewed evaluates only how well a defence catches attacks and
says nothing about how often it wrongly blocks legitimate users during a surge.

These three observations converge on the same missing design. What the literature lacks is an in-kernel,
line-rate defence that filters cheaply on all traffic, escalates only the genuinely ambiguous slice to a
learned model, adapts its threshold live through the shared map, and — decisively — is evaluated on the
false positives it inflicts on a legitimate flash crowd. Each reviewed family supplies one piece of this
picture: the eBPF filters supply the speed, the machine-learning detectors supply the discrimination,
the statistical schemes supply the idea of adaptation, and the flash-crowd studies supply the evaluation
question. No single reviewed system supplies all four together. That absence is the gap this research
sets out to fill, and it shapes directly the objectives stated in Chapter 1 and the system specified in
the chapters that follow.
</content>
