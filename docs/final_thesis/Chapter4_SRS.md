# CHAPTER 4 - SYSTEM REQUIREMENT SPECIFICATION

## 4.1 Chapter Overview

Having established what the research is trying to show, this chapter sets out what the
system itself needs to do to show it. It begins by identifying who the system serves and
what each of them needs from it, then explains how the research objectives from Chapter
One were turned into something that could actually be built and measured. The system is
then modelled from several angles - who uses it, how its parts are structured, how a
packet moves through it, and how its components talk to one another - before the chapter
closes with a concrete list of functional and non-functional requirements that the
implementation in Chapter Five was built against.

## 4.2 Stakeholder Analysis

The **operator** is the person who would run the system in front of a real service. Their
concern is straightforward but genuinely hard to satisfy at the same time: stop attacks,
and do not stop paying customers. Everything about the adaptive threshold and the
selective escalation tier exists because of this one stakeholder's conflicting needs.

The **legitimate end user** never touches the system directly and is mostly unaware it
exists, but is the stakeholder the flash-crowd evaluation in Chapter Six is really about.
A defence that is only judged on how well it stops attackers has, in a sense, forgotten
this stakeholder entirely, which is precisely the gap identified in Chapter Two.

The **attacker** is modelled as an adversarial actor rather than a beneficiary. Their
only interest, from the system's point of view, is to be recognised and dropped as
quickly and as cheaply as possible.

The **researcher**, and by extension the **examiner**, are stakeholders in the evaluation
itself. Their shared interest is that whatever the system claims to do can actually be
demonstrated, live, on request - which shaped a number of decisions later in this chapter
and in Chapter Five, including the choice to keep the kernel-side logic deliberately
simple enough that every line of it can be explained and defended.

## 4.3 Operationalisation Process

Because this is a systems and experimentation project rather than a survey-based one,
"gathering data" here means something different from handing out a questionnaire. Two
instruments do this job. The CIC-IDS-2017 dataset operationalises the "analyse" and
"design and develop" objectives for the machine-learning tier: its labelled benign and
attack flows are what the decision tree is trained against and measured on, and its
column set determined which features were realistically available to learn from. The
generated attack and flash-crowd traffic, together with the counters read directly out of
the kernel maps, operationalises the "evaluate" objective - firing known, labelled
traffic at the running system and recording what happens to it is what turns the research
question into a number that can be compared across configurations.

One thing worth being upfront about here, because it shaped a real decision later in
implementation: reading results back through the dashboard's own API turned out to be an
unreliable way to measure the system, since the dashboard's own polling traffic is itself
subject to the same threshold it is trying to report on. Once this was noticed, the
measurement approach was changed to read the BPF maps directly with bpftool, which cannot
itself be affected by the filtering under test. This is discussed further in Chapter Six,
but it is worth flagging here as it directly affected how the requirements below were
validated.

## 4.4 System / Model Analysis

### 4.4.1 Use Case Diagram

Three actors interact with the system. The **Operator** views live status, sets the
threshold manually, enables or disables adaptive mode, and clears counters, all through
the dashboard and its underlying API. The **Attacker** is an external actor whose packets
enter the system and are acted upon, rather than someone who operates it. The **Traffic
Generator** actor, used only for demonstration and evaluation, drives the "start attack"
and "start flash crowd" use cases. Internally, and not triggered by any external actor
directly, the system also filters packets, escalates ambiguous sources to the classifier,
and adapts the threshold - each of these is best modelled as an internal use case
included by the packet-arrival flow rather than something a human actor invokes.

### 4.4.2 Class Diagram

The userspace side of the system is built around a small number of classes, each mapping
onto one Python module, which keeps the design easy to reason about even though several
of them run as independent background threads. `BpfSession` owns the attached XDP program
and its maps, and is the only class that talks to the kernel directly - it exposes
methods to attach, detach, read totals, read the top talking sources, and get or set the
threshold. `Collector` holds a reference to a `BpfSession`, runs on a one-second timer,
and is responsible for persisting a snapshot to the database and for calling the
classifier when it finds a source sitting in the ambiguous band. `ControlLoop` also holds
a `BpfSession` reference and, independently of the collector, computes a new threshold
from a smoothed traffic-rate estimate and writes it back through the session. The
classifier is a small module that loads a trained decision tree once, on first use, and
exposes a single `classify_flow` function. `DB` wraps both the local SQLite database and
the optional MongoDB Atlas mirror behind one interface, and `API` sits above all of these,
exposing them to the dashboard over HTTP.

### 4.4.3 Activity Diagram

The most important single activity in the whole system is what happens to one packet on
the fast path. It begins the moment a packet reaches the XDP hook. The program first
checks that the Ethernet header, and then the IPv4 header, sit entirely within the bounds
of the packet - the eBPF verifier requires this check before either header can be safely
read, and any packet that fails it, or that simply is not IPv4, is passed through
untouched. Assuming both checks succeed, the source address is read, that source's
counter in the `ip_count` map is incremented, and the current threshold is read from the
`config` map. The activity then reaches its one decision point: if the incremented count
has reached the threshold, the packet is dropped and the "dropped" tally is incremented;
otherwise it is passed and the "passed" tally is incremented. A second activity, running
independently in userspace on its own timer, periodically reads the maps, checks whether
any source has moved into the ambiguous band, and, for any that have, hands that source
off to the classifier.

### 4.4.4 Sequence Diagrams

Three sequences cover the system's main interactions. The **filtering sequence** shows a
packet reaching the XDP program, the program updating `ip_count` and reading `config`,
and a verdict being returned - entirely inside the kernel, with no userspace involvement
at all. The **escalation sequence** shows the collector reading the maps on its tick,
finding a source in the ambiguous band, calling `classify_flow` with that source's
features, and recording the returned label as an event. The **adaptation sequence** shows
either the operator issuing a manual threshold change through the API, or the control
loop computing one on its own from the smoothed traffic rate, and in both cases ends with
the new value being written into the `config` map, ready to be read by the very next
packet.

### 4.4.5 Deployment Diagram

The whole system is deployed on a single host, which keeps this diagram simple by design.
One node represents kernel space, holding the XDP program and its three maps; a second
represents userspace, holding the Python services, the local SQLite file, and the
connection out to MongoDB Atlas; a third, external node represents the operator's browser,
reaching the API over HTTP.

## 4.5 Proposed System Architecture

The architecture is the two-tier design carried through the rest of this dissertation.
Tier 1 is the XDP program: cheap, always-on, and running on every packet. Tier 2 is the
decision tree: selective, running only on the minority of sources the first tier cannot
confidently resolve either way. The two tiers never call each other directly - they are
joined only by three BPF maps, which hold the per-source counts, the live threshold, and
the running totals. Around this core sit the collector and control loop, which read and
write those maps from userspace on independent timers, the database layer, which keeps a
durable record of what happened, and the API and dashboard, which make all of this
visible to an operator. What makes the design work as a whole is the strict separation
between the fast, bounded kernel path and the slower, unbounded userspace path, with nothing
crossing that boundary except the contents of the maps.

## 4.6 Functional and Non-functional Requirements

**Functional requirements.** The system shall: (F1) attach an eBPF program at the XDP
hook and maintain a per-source-IP packet count; (F2) drop a source's packets once its
count reaches the current threshold, and pass them otherwise; (F3) allow the threshold to
be changed at runtime, with the new value taking effect on the next packet, without
reloading the XDP program; (F4) periodically read the kernel counters and persist them to
a database; (F5) identify sources whose count falls within a defined ambiguous band and
classify those sources with a decision tree trained offline; (F6) when adaptive mode is
enabled, compute and write an updated threshold from recent traffic without operator
intervention; (F7) expose the system's live state through a REST API, a web dashboard,
and a command-line tool; and (F8) provide tools to generate both attack traffic and
legitimate flash-crowd traffic for demonstration and evaluation.

**Non-functional requirements.** The system should: (N1) keep its per-packet kernel-side
work cheap and bounded enough to satisfy the eBPF verifier, with no unbounded loops and no
floating-point arithmetic; (N2) keep all heavier userspace work off the packet path, so
that the speed of the collector, the control loop, or the classifier never affects packet
forwarding; (N3) remain stable under sustained, high-rate traffic; (N4) treat the BPF map
layout as a single shared contract between the kernel program and every userspace
component that reads or writes it, so the two sides cannot silently drift apart; (N5) be
reproducible, so that a given traffic scenario produces comparable results on repeated
runs; and (N6) present its live state clearly enough that an operator, glancing at the
dashboard for a few seconds, can tell whether the system is under attack.

## 4.7 Chapter Summary

This chapter turned the aim and objectives of Chapter One into a concrete specification.
It set out who the system serves - the operator, the legitimate user who never sees it,
the attacker, and the researcher who has to be able to demonstrate every claim made about
it - and explained how the CIC-IDS-2017 dataset and the generated attack and flash-crowd
traffic operationalise the research objectives in place of a questionnaire. It modelled
the system through use case, class, activity, sequence, and deployment views, set out the
two-tier architecture with the BPF maps as the single bridge between its halves, and
closed with the functional and non-functional requirements the implementation was built
to satisfy. Chapter Five now describes how that implementation was actually carried out.
</content>
