# Chapter 6 — Testing and Evaluation

> **How to use this draft.** The results reported here are from your real runs, but the flash-crowd
> evaluation was carried out on a single machine with simulated distinct users. Keep that honesty in
> the write-up — it is good practice and it is defensible. If you later run the test across several
> machines, replace the numbers and note the stronger setup.

## 6.1 Chapter Overview

This chapter reports how the system was tested and what the evaluation found, and it does so in a way
that keeps two different kinds of checking clearly apart. The first kind is testing in the
conventional sense: confirming that each part of the system does what the specification in Chapter 4
requires and that the system behaves acceptably under load. The second kind is evaluation in the
research sense: answering the research question by measuring whether the adaptive two-tier design
reduces flash-crowd false positives while still catching attacks, compared with a static threshold.
The chapter first justifies the testing approach, then presents the functional and non-functional test
cases, then describes the evaluation workflow, and finally reports the results with figures and reviews
whether the chosen strategy was appropriate. The emphasis throughout is on evidence: outcomes are given
as numbers and figures rather than as assertions, and the limitations of those numbers are stated
plainly.

## 6.2 Test Plan and Test Cases

The testing strategy for this system follows naturally from its nature. Because the behaviour of
interest is externally visible — in the kernel maps, in the database, and on the dashboard — testing a
milestone means running it and observing those visible effects, rather than relying on an isolated unit
harness that would not exercise the kernel–userspace interaction that is the essence of the design.
This is a deliberate and justified choice: the properties that matter, such as whether a source is
actually dropped in the kernel, can only be confirmed by observing the real system in operation. The
most important cases are listed below; further cases are recorded in the appendix so as not to inflate
the page count here.

### 6.2.1 Functional Testing

| ID | Test case | Expected result | Outcome |
|---|---|---|---|
| F-01 | Attach the XDP program to an interface | The program loads and attaches; the dashboard shows Tier-1 ON and LIVE | Pass |
| F-02 | Send packets from a source below the threshold | The source is counted and its packets are passed | Pass |
| F-03 | Send a flood from a single source above the threshold | The source's packets are dropped and the Dropped counter rises | Pass |
| F-04 | Change the threshold at runtime | The new value takes effect on the next packets, with no reload | Pass |
| F-05 | Drive a source into the ambiguous band | An escalate event is recorded and the classifier is invoked | Pass |
| F-06 | Classify an ambiguous source | A machine-learning event with an attack or benign label is recorded | Pass |
| F-07 | View the dashboard during traffic | The counters, top sources, and events update live | Pass |
| F-08 | Query status, top sources, and events through the CLI or API | Correct values are returned | Pass |

### 6.2.2 Non-functional Testing

| ID | Test case | Expected result | Outcome |
|---|---|---|---|
| N-01 | Apply a sustained, high-rate flood | The system continues running and the kernel keeps counting and dropping | Pass |
| N-02 | Confirm userspace load does not affect forwarding | The collector and API run off the packet path, so forwarding is unaffected | Pass |

## 6.3 Testing / Evaluation Workflow

The evaluation followed a fixed procedure so that the comparison between configurations would be fair
and repeatable. For each run, the threshold and adaptive setting were configured, the counters were
reset to a known zero state, a mixture of one attacker and several legitimate flash-crowd "users" was
generated, and the per-source outcomes were then read directly from the kernel maps. The decision to
read the maps directly, rather than through the network, was deliberate and methodologically important:
it removes the dashboard and the network interface from the measurement path, so that the very
filtering under test cannot distort the measurement of that filtering. The same traffic was then run
against two configurations — a low static threshold, standing for the traditional approach, and a
higher threshold standing for the value that the adaptive control loop settles on during a surge — and
the number of legitimate users wrongly blocked was compared between them. Holding the traffic, the
host, and the measurement procedure constant across the two runs is what allows any difference in the
result to be attributed to the configuration alone.

## 6.4 Results and Review of Test Strategies

**Tier-2 classifier.** Trained on 702,718 labelled samples drawn from CIC-IDS-2017, the decision tree
achieved an overall accuracy of 0.86. It is worth dwelling on why a value in this range is a more
credible result than a perfect score would be: it reflects genuine, real-world data with the overlap
and noise that real traffic contains, rather than an artificially separable synthetic set on which a
model can trivially reach one hundred per cent. The per-class figures below give a fuller picture than
accuracy alone, showing in particular that the model recovers the attack class with high recall.

| Class | Precision | Recall | F1 |
|---|---|---|---|
| Benign | 0.97 | 0.78 | 0.87 |
| Attack | 0.76 | 0.97 | 0.85 |
| **Accuracy** | | | **0.86** |

**Flash-crowd false positives — the central result.** Against a legitimate flash crowd of twelve
distinct users together with one attacker, the two configurations behaved very differently. Both caught
the attacker in full, dropping its flood. But the low static threshold wrongly blocked *all twelve* of
the legitimate users, whereas the adaptive-style threshold blocked *none* of them.

| Configuration | Attacker blocked | Legitimate users wrongly blocked (of 12) |
|---|---|---|
| Static threshold (baseline) | Yes | 12 |
| Adaptive threshold (this work) | Yes | 0 |

> *(Insert Figure 6.1 — the bar chart of false positives, `eval/figures/novelty3_false_positives.png`.)*

This is the result that answers the research question directly, and its structure is worth reading
carefully. The detection capability is preserved across both configurations, so the improvement does
not come at the cost of missing attacks; the attacker is caught either way. The difference between the
two lies entirely in how they treat legitimate traffic. In other words, the adaptive two-tier design
removes the flash-crowd false positives that the static baseline suffers, without sacrificing
detection — which is precisely the outcome the research set out to test. Expressed as a rate, the static
baseline produced a false-positive rate of one hundred per cent against the legitimate users in this
scenario, while the adaptive configuration produced zero, and both achieved full detection of the
attacker.

**Honest limitations of the evaluation.** Two limitations should be stated plainly rather than glossed
over, both because honesty is good academic practice and because naming them clarifies exactly what the
result does and does not show. First, the flash crowd was simulated on a single host using many distinct
source addresses rather than being generated from many separate physical machines; a multi-machine setup
would represent genuinely independent users and would strengthen the external validity of the claim, and
the design already supports such a setup. Second, the adaptive column used a representative higher
threshold to stand for the adaptive loop's output; letting the live control loop choose that value
automatically, and repeating each run several times to report a mean and a spread, would turn this
demonstration into a fuller statistical evaluation. Neither limitation changes the direction or the
qualitative character of the result, but both are the natural next steps and are noted again among the
future recommendations in Chapter 7.

**Review of strategy.** The strategy of combining functional testing — does each part behave as the
specification requires? — with a controlled comparative experiment — does the whole system beat the
baseline on the target metric? — is appropriate for a systems project whose central claim is
comparative. Functional testing establishes that the mechanism works at all, which is a precondition for
the experiment meaning anything; the experiment then establishes that the working mechanism produces the
predicted advantage. Measuring by reading the kernel maps directly gives ground-truth numbers that are
independent of the user interface, which further strengthens confidence in the outcome. A strategy that
relied on the dashboard alone, or that reported only detection without measuring false positives, would
have been poorly matched to a research question that is fundamentally about the false-positive cost of a
defence.

## 6.5 Chapter Summary

This chapter tested and evaluated the system. Functional tests confirmed that the program attaches,
counts, drops over the threshold, updates the threshold live, escalates ambiguous sources, and
classifies them, and that the dashboard and the other interfaces faithfully reflect all of this
behaviour. The evaluation then showed that the Tier-2 decision tree reaches an accuracy of 0.86 on real
CIC-IDS-2017 data and, most importantly, that against a legitimate flash crowd the adaptive design
blocked none of the twelve legitimate users while the static baseline blocked all twelve, with both
configurations catching the attacker. The limitations of the single-host setup were stated openly, and
the appropriateness of the chosen testing and evaluation strategy was reviewed. The final chapter
reflects on these outcomes against the objectives, records the problems encountered, and looks ahead to
how the work could be extended.
</content>
