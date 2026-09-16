# Chapter 4 — System Requirement Specification

> **How to use this draft.** The requirements, stakeholders, and use cases below describe the
> system you actually built. The UML diagrams (use case, class, activity, sequence, deployment)
> are described in enough detail for you to *draw* them; please create them in a tool such as
> draw.io and insert each figure where marked, then confirm they match your code. Drawing them
> yourself also means you can explain them in the viva.

## 4.1 Chapter Overview

This chapter turns the aim and objectives from Chapter 1 into a concrete specification of what the
system must do and for whom. It begins by identifying the stakeholders and the concerns each of
them brings to the system, because those concerns are what ultimately justify the requirements.
It then explains how the research objectives were made measurable through the dataset and the
generated traffic, an activity that stands in this systems project in place of the questionnaire
or interview used in more survey-oriented work. The system is then modelled from several
complementary angles using the standard UML views — use case, class, activity, sequence, and
deployment — so that its behaviour, its structure, and its distribution across the machine are
each made explicit. Finally the chapter presents the proposed architecture and states the
functional and non-functional requirements that the implementation described in Chapter 5 was
built to satisfy.

## 4.2 Stakeholder Analysis

Although the prototype is a research artefact rather than a deployed commercial product, it is
useful and legitimate to reason about the people and roles whose interests the system touches,
because those interests shaped what the system was required to do.

The **service operator**, or defender, is the primary stakeholder. This is the administrator who
would run Cerberus in front of a service they are responsible for keeping available. Their central
concern is twofold and, importantly, in tension: they need to stop attacks, and they need to keep
the service reachable by genuine users at the same time. From this concern flow several
requirements — that the system act quickly, that it not over-block during a surge, and that it give
the operator enough visibility to understand and trust what it is doing.

The **legitimate end users** are an indirect but central stakeholder. They never interact with
Cerberus and are usually unaware of its existence, yet the entire flash-crowd component of the
research exists to protect them. Their interest is simply to reach the service they came for, even
during a busy moment, and it is precisely this interest that a naive, volume-only defence
threatens. Treating end users as a stakeholder in their own right is what elevates false positives
from a technical afterthought to a first-class requirement.

The **attacker** appears in the model as an adversarial actor rather than a beneficiary. Their goal
is to deny service, and the system's requirement in respect of them is to recognise and drop their
traffic. Modelling the attacker explicitly is useful because it clarifies which behaviours the
system must treat as hostile and which it must be careful to leave alone.

Finally, the **researcher and developer** — the author — and the **supervisor and examiner** are
stakeholders in the evaluation rather than in day-to-day operation. Their shared interest is that
the system produce clear, honest, and reproducible measurements capable of answering the research
question, which translates into requirements for reproducibility, for observable behaviour, and
for a clean separation between the effect being measured and the means of measuring it.

## 4.3 Operationalisation Process

Because this is an experimental systems project rather than a survey of opinion, the process of
gathering data took the form of a labelled dataset and controlled measurement rather than a
questionnaire or interview. It is nevertheless important to show how each means of gathering data
maps onto a research objective, since that mapping is what justifies treating the resulting
requirements as valid.

The **CIC-IDS-2017 dataset** operationalises the analytical and design objectives for the
machine-learning tier. Its labelled records of benign and attack flows are the material from which
the decision tree learns and against which its accuracy is judged, so the dataset is the concrete
instrument that turns the abstract objective of "classify ambiguous traffic" into something that
can be trained and measured. The **generated attack and flash-crowd traffic**, together with the
counters read from the kernel, operationalises the evaluation objective. Firing controlled,
known traffic at the system and recording how much of it is dropped is what converts the research
question into numbers that can be compared between configurations. The validity of these choices
rests on two supports: that CIC-IDS-2017 is an accepted benchmark within the field, and that the
generated traffic is controlled and repeatable, so that a measured difference in outcome can be
attributed to the system's configuration rather than to variation in the input. Reviewing the
results of this data gathering confirmed that both instruments were fit for purpose — the dataset
was rich enough to train a usable classifier, and the generated traffic was controllable enough to
produce a clean comparison — which is what justifies the requirements derived from them.

## 4.4 System / Model Analysis

### 4.4.1 Use Case Diagram

The system is modelled with three external actors. The **Operator** interacts with the running
system through the dashboard and the API. The **Attacker** is an external actor whose packets enter
the system from outside and are acted upon rather than an actor who operates the system. For the
purposes of evaluation, a **Traffic Generator** actor represents the tooling that produces both
attack and legitimate-surge traffic. The automated tiers of the system are not external actors;
they act internally in response to traffic and to the operator's settings.

The operator's use cases are: *view live status*, which retrieves the current counters, top
sources, and events; *set threshold manually*, which writes a chosen threshold into the kernel;
*enable or disable adaptive control*, which turns the automatic threshold adjustment on or off;
and *clear counters*, which resets the per-source counts between runs. The evaluation use cases,
driven by the Traffic Generator, are *start attack traffic* and *start flash-crowd traffic*.
Internally, and triggered by incoming packets rather than by an actor, the system also *filters
packets*, *escalates ambiguous sources* to the classifier, and *adapts the threshold*; these are
best shown with «include» relationships from the operator-facing or traffic-driven cases they
support.

> *(Insert Figure 4.1 — use case diagram. Connect the Operator to the four operator use cases, the
> Traffic Generator to the two demonstration use cases, and show the internal "filter", "escalate",
> and "adapt" cases with «include» relationships where appropriate.)*

### 4.4.2 Class Diagram

The userspace side of the system is organised around a small set of cooperating classes whose
responsibilities mirror the files in the backend, an arrangement that keeps the design easy to
reason about. The `BpfSession` class owns the connection to the loaded kernel program and its maps
and is the single point through which the rest of the system reads or writes kernel state; it
exposes operations to read the global totals, read the top sources, get and set the threshold, and
clear the counters. The `Collector` class runs on a timer and depends on a `BpfSession` to read the
maps; it persists each snapshot through the `DB` helper and, when it finds an ambiguous source,
calls the classifier. The `ControlLoop` class likewise depends on a `BpfSession`, computing an
updated threshold from the recent traffic and writing it back into the map. The classifier is a
module that loads the trained decision tree once and exposes a single `classify_flow` operation.
The `API` layer holds references to these objects and exposes their capabilities over HTTP to the
dashboard and the command-line tool. The key relationships are therefore associations of use —
`Collector` and `ControlLoop` each use a `BpfSession`, and `Collector` uses both the `DB` and the
classifier — with the `API` acting as the outward-facing façade over the whole set.

> *(Insert Figure 4.2 — class diagram showing BpfSession, Collector, ControlLoop, DB, the
> classifier module, and the API, with their principal methods and the "uses" associations between
> them.)*

### 4.4.3 Activity Diagram

The single most important activity in the system is the life of one packet on the fast path. The
activity begins when a packet reaches the XDP hook. The program first checks that the Ethernet
header and then the IPv4 header lie wholly within the packet's bounds; if either check fails, the
packet is passed unmodified, because the verifier requires such bounds checks and because
non-conforming or non-IPv4 traffic is outside the scope of the filter. Assuming the checks succeed,
the program reads the source address, increments that source's counter, and reads the current
threshold from its map. It then reaches the central decision point: if the source's count has
reached the threshold, the program records a drop and returns the drop verdict; otherwise it
records a pass and returns the pass verdict. A second, slower activity runs independently in
userspace: on each timer tick the collector reads the maps, decides whether any source now falls
within the ambiguous band, and, for any that do, escalates them to the classifier. Presenting these
as two separate activities reflects the real separation between the fast kernel path and the slow
userspace path.

> *(Insert Figure 4.3 — activity diagram of the packet path, showing the two bounds checks, the
> counter increment, the threshold comparison, and the drop/pass branch, with the userspace
> escalation activity shown alongside.)*

### 4.4.4 Sequence Diagrams

Three sequences capture the system's most important interactions, and together they cover the fast
path, the escalation path, and the adaptation path.

The **filtering sequence** shows a packet arriving at the XDP program, the program updating the
per-source counter in the `ip_count` map and reading the threshold from the `config` map, and a
verdict being returned to the kernel — the entire interaction taking place within the hot path and
without any involvement from userspace.

The **escalation sequence** shows the `Collector` reading the maps on its tick, identifying a source
whose count lies within the ambiguous band, calling `classify_flow` on that source's features,
receiving an attack-or-benign label in return, and recording the result as an event. This sequence
makes visible the selective nature of the design: only ambiguous sources ever reach the classifier.

The **adaptation sequence** shows the two ways the threshold can change. In one, the operator issues
a *set threshold* request through the API, which writes the new value into the `config` map. In the
other, the `ControlLoop` computes a new threshold from recent traffic and writes it into the same
map. In both cases the sequence ends with the kernel reading the updated value on the next packet,
which illustrates the reload-free nature of the update.

> *(Insert Figures 4.4–4.6 — the filtering, escalation, and adaptation sequence diagrams, each
> mapped to the use case it realises.)*

### 4.4.5 Deployment Diagram (optional)

The deployment is a single host, which keeps the picture simple. Within that host, one node
represents kernel space and contains the XDP program together with the three BPF maps; a second
node represents userspace and contains the Python services and the SQLite database. A separate node
represents the operator's web browser, which communicates with the API over HTTP. The diagram makes
clear that although the system spans the kernel and userspace boundary, it runs on one machine, and
that the only channel across that internal boundary is the set of BPF maps.

> *(Insert Figure 4.7 — deployment diagram, if included.)*

## 4.5 Proposed System Architecture

The architecture is the two-tier design that runs throughout this dissertation. Tier 1 is the XDP
program in the kernel, which performs cheap per-source counting and thresholded dropping on every
packet that arrives. Tier 2 is the userspace decision tree, which is invoked only for the ambiguous
minority of sources that Tier 1 cannot confidently resolve. The two tiers do not call one another
directly; they communicate solely through the BPF maps, which hold the per-source counts, the live
threshold, and the global totals. Arranged around this core are the collector, which reads the maps
on a timer and persists what it finds; the control loop, which writes an updated threshold back into
the kernel; the SQLite database, which is the local source of truth for historical data; the REST
API, which exposes the state; and the dashboard, which presents it to an operator. The defining
characteristic of the architecture is this strict separation of a fast hot path from a slow cold
path, joined only by shared memory, which is what allows the system to be fast and discriminating
at once.

> *(Insert Figure 4.8 — system architecture. A clean version of this diagram already exists in
> `docs/HOW_IT_ALL_CONNECTS.md`; redraw it for the thesis with kernel and userspace clearly
> separated and the maps shown as the bridge between them.)*

## 4.6 Functional and Non-functional Requirements

**Functional requirements.** The system shall: (F1) attach an eBPF program at the XDP hook and count
packets per source IP address; (F2) drop packets from a source once its count reaches the current
threshold, and pass them otherwise; (F3) allow the threshold to be updated at runtime, taking effect
on the next packet, without reloading the kernel program; (F4) read the kernel counters periodically
and persist them to local storage; (F5) identify sources whose counts fall within the ambiguous band
and classify those sources with the decision tree; (F6) adjust the threshold automatically from
recent traffic when adaptive mode is enabled; (F7) expose the live state through a REST API and a
dashboard, and through a command-line tool; and (F8) generate controlled attack and flash-crowd
traffic for the purposes of evaluation.

**Non-functional requirements.** The system should: (N1) perform its per-packet work cheaply enough
to run on the hot path, remaining within the eBPF verifier's limits on program size and control flow;
(N2) keep the userspace services off the packet path, so that their execution speed does not affect
packet forwarding; (N3) remain stable during sustained high-rate traffic, continuing to count and
drop correctly under load; (N4) resolve the kernel–userspace contract through a single shared map
layout, so that the two sides cannot drift out of agreement; (N5) be reproducible, relying on a fixed
dataset and controlled, repeatable traffic so that results can be re-obtained; and (N6) be usable,
presenting its state clearly enough that an operator can understand what the system is doing at a
glance. The functional requirements describe what the system must do to realise the design, while the
non-functional requirements capture the qualities — speed, stability, reproducibility, and clarity —
without which the functional behaviour would not be trustworthy.

## 4.12 Chapter Summary

This chapter specified the system. It identified the operator, the protected end users, the attacker,
and the research stakeholders, and it explained how the dataset and the generated traffic make the
research objectives measurable in place of a questionnaire. It modelled the system through use case,
class, activity, sequence, and deployment views, each of which exposes a different facet of the
design, and it presented the two-tier architecture with the BPF maps as its central bridge. Finally,
it stated the functional requirements that define what the system must do and the non-functional
requirements that define how well it must do them. The next chapter describes how these requirements
were implemented in practice.
</content>
