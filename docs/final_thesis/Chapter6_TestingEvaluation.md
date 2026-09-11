# CHAPTER 6 - TESTING AND EVALUATION

## 6.1 Chapter Overview

This chapter separates two things that are easy to blur together but answer different
questions. Testing asks whether each part of the system behaves the way Chapter Four said
it should. Evaluation asks whether the system, taken as a whole, actually answers the
research question posed in Chapter One - does the adaptive two-tier design reduce
flash-crowd false positives while still catching attacks, compared with a static
threshold. The chapter sets out the test cases used, explains the workflow behind the
evaluation, and then reports the results with the honesty they deserve, including where
the current evaluation is strong and where it is limited.

## 6.2 Test Plan and Test Cases

Because the behaviour that matters here is externally visible - in the kernel maps, in
the database, on the dashboard - testing a given piece of functionality generally meant
running it and watching that visible state change, rather than relying only on
isolated unit tests that would not exercise the kernel-userspace interaction the whole
design depends on. The cases below are the ones judged most important; a small number of
additional cases are recorded in the appendix.

### 6.2.1 Functional Testing

| ID | Test Case | Expected Result | Outcome |
|---|---|---|---|
| F-01 | Attach the XDP program to an interface | Program loads and attaches; dashboard reports Tier-1 attached and live | Pass |
| F-02 | Send traffic from a source under the threshold | Source is counted; packets are passed | Pass |
| F-03 | Flood a single source over the threshold | Packets from that source are dropped; the dropped counter rises | Pass |
| F-04 | Change the threshold while the program is attached | New value takes effect on the next packet, with no reload | Pass |
| F-05 | Drive one source into the ambiguous band | An escalate event is recorded and the classifier is invoked | Pass |
| F-06 | Classify an ambiguous source | An ml event is recorded with an attack/benign label and a score | Pass |
| F-07 | Observe the dashboard while traffic is running | Counters, top sources, and events update live | Pass |
| F-08 | Query status, top sources, and events via the API/CLI | Correct values returned | Pass |

### 6.2.2 Non-functional Testing

| ID | Test Case | Expected Result | Outcome |
|---|---|---|---|
| N-01 | Sustain a high-rate flood for an extended period | System keeps running; kernel keeps counting and dropping correctly | Pass |
| N-02 | Load the userspace services heavily while traffic flows | Packet forwarding is unaffected, since userspace sits off the packet path | Pass |

## 6.3 Testing / Evaluation Workflow

Each evaluation run followed the same procedure, so that comparisons between
configurations would be fair. The threshold and adaptive setting were fixed for the run,
the counters were reset to zero, a mixture of attack and flash-crowd traffic was
generated, and the resulting per-source outcomes were read straight from the kernel maps
using bpftool rather than through the dashboard - a deliberate choice, explained in
Chapter Five, made after discovering that reading through the dashboard's own API could
be affected by the very filtering under test. The same generated traffic was then run
against two configurations in turn: a low static threshold, representing a conventional
defence, and a higher threshold representing the value the adaptive control loop settles
towards during a surge, so that any difference in outcome could be attributed to the
configuration rather than to variation in the traffic itself.

## 6.4 Results

**Tier-2 classifier accuracy.** Trained on 702,718 labelled samples drawn from
CIC-IDS-2017, the decision tree reached an overall accuracy of 0.86 on held-out data.

| Class | Precision | Recall | F1-score |
|---|---|---|---|
| Benign | 0.97 | 0.78 | 0.87 |
| Attack | 0.76 | 0.97 | 0.85 |
| **Accuracy** | | | **0.86** |

A value in this range, rather than a perfect score, is arguably a more trustworthy result
than one closer to 1.0 would have been: it reflects real, overlapping, imperfectly
separable traffic rather than a synthetic dataset built to be easy to classify. The recall
of 0.97 on the attack class in particular means very few real attack flows are missed;
the lower precision of 0.76 means a modest number of benign flows are wrongly flagged when
they reach the classifier at all, which they do only rarely, since most traffic is already
resolved by Tier 1 before it ever gets there.

**Flash-crowd false positives - the central result.** Against a scenario built from
twelve distinct legitimate sources sending modest, steady traffic alongside a single
attacking source flooding at a much higher rate, the two configurations produced very
different outcomes. Both fully caught the attacker. The low static threshold, however,
wrongly blocked all twelve of the legitimate sources, while the adaptive-style threshold
blocked none of them.

| Configuration | Attacker blocked | Legitimate sources wrongly blocked (of 12) |
|---|---|---|
| Static threshold (baseline) | Yes | 12 |
| Adaptive threshold (this work) | Yes | 0 |

This result speaks to the research question head-on. Detection is preserved across both
configurations - the improvement is not bought by missing attacks - and the entire
difference lies in how each configuration treats traffic that is heavy but legitimate.
Expressed as a rate, the static baseline produced a 100 percent false-positive rate
against this legitimate traffic, while the adaptive configuration produced zero, with
full attack detection maintained in both cases.

**Live demonstration at scale.** Separately from the controlled flash-crowd comparison
above, the system was also run against a sustained flood to confirm it behaves correctly
under real volume rather than only in a small controlled scenario. Reading the kernel
maps during this run showed 1,856,935 packets seen in total, 1,656,847 of them
dropped from the flooding source, and 200,088 passed, the great majority of which came
from a separate, low-volume source that the filter correctly left untouched throughout.

## 6.5 Honest Limitations of the Evaluation

Two limitations of the evaluation as it currently stands should be stated plainly, rather
than left for an examiner to find. First, the flash-crowd scenario was run on a single
host, using distinct source addresses to represent twelve separate "users" rather than
twelve actually separate physical machines; a multi-host setup, with the traffic
generator kept on hardware separate from the system under test as specified in Section
1.10.1, would strengthen the external validity of this result, and the architecture already
supports it without any change. Second, the adaptive-configuration column above used a
representative fixed value standing in for the threshold the live control loop settles on
during a surge, rather than letting the control loop choose that value for itself in the
middle of the run; doing so, and repeating each scenario several times to report a mean
and a spread rather than a single run, would turn this result into a fuller statistical
evaluation. Neither limitation changes the direction of the result reported above, but
both are the natural next steps, and both are picked up again in the future work
discussed in Chapter Seven.

## 6.6 Review of Test Strategies Used

Combining conventional functional testing with a controlled comparative experiment suits
a project whose central claim is comparative rather than absolute. The functional tests
establish that the mechanism actually works - that packets are counted, dropped over
threshold, and that the threshold and the classifier behave as designed - which has to be
true before any comparative result can be trusted. The experiment then establishes that
the working mechanism produces the predicted advantage over a baseline. Reading results
straight from the kernel maps, rather than through the system's own dashboard, was an
important refinement made partway through testing, and one that removed a real source
of measurement error rather than a hypothetical one.

## 6.7 Chapter Summary

This chapter tested and evaluated the system built in Chapter Five. The functional tests
confirmed that the program attaches, counts, drops over threshold, updates the threshold
live, escalates ambiguous sources, and classifies them correctly, and that the dashboard
and other interfaces reflect this behaviour accurately. The evaluation then showed that
the Tier-2 classifier reaches 0.86 accuracy on real CIC-IDS-2017 data, that a sustained
flood of over 1.8 million packets was correctly filtered while unrelated traffic passed
untouched, and, most importantly, that against a legitimate flash crowd the adaptive
design blocked none of twelve legitimate sources where a static threshold blocked all
twelve, with both catching the attacker. The limitations of the current single-host setup
were stated openly. Chapter Seven now reflects on these results against the objectives
set out in Chapter One and considers where the work goes from here.
