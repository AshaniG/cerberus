# Chapter 7 — Concluding Remarks

> **How to use this draft.** The reflections here are written in the first person, as a conclusion
> should be. Please make them genuinely yours — adjust anything that does not match your own
> experience, and keep the honesty about what worked and what was hard, because examiners value it.

## 7.1 Accomplishment of the Research Objectives

The research set out to design, implement, and evaluate a two-tier, adaptive, in-kernel DDoS defence
that protects legitimate flash crowds, and each of the four objectives stated in Chapter 1 was met.
It is worth reviewing each in turn, drawing on the outcomes of the testing chapter rather than on
assertion.

The first objective, to *identify* the constraints of the eBPF/XDP environment and the shortcomings of
existing defences, was achieved through the literature review and, just as importantly, through direct
experience of the verifier's limits during development. Working within those limits first-hand made
concrete what the review described in the abstract, and it confirmed why a bounded decision tree, rather
than a heavier model, is the appropriate choice near the kernel. The second objective, to *analyse* how
flash crowds and attacks differ and how threshold strategies trade detection against false positives,
was addressed both in the review and, decisively, in the experiment, which showed the trade-off in
concrete numbers rather than in principle. The third objective, to *design and implement* the system,
produced a working prototype comprising a Tier-1 XDP filter, a Tier-2 decision tree trained on
CIC-IDS-2017, and a control loop that updates the kernel threshold live through the BPF maps; each of
these parts was demonstrated to work on real traffic in Chapter 5. The fourth objective, to *evaluate*,
produced the central result: against a legitimate flash crowd, the adaptive design blocked none of the
twelve legitimate users while the static baseline blocked all twelve, and both configurations caught the
attacker.

Triangulating the three independent strands of evidence — the functional tests that confirm the
mechanism works, the classifier's 0.86 accuracy on real benchmark data, and the flash-crowd comparison
that shows the false-positive advantage — the body of evidence supports the claim that the design
maintains detection while reducing flash-crowd false positives relative to a static baseline. Because
these strands are independent of one another, their agreement gives more confidence than any one of them
could alone. The aim stated in Chapter 1 was therefore accomplished.

## 7.2 Problems Encountered

The project met several real obstacles, and working through them was itself a substantial part of the
learning. The first was environmental. On the particular kernel of the development machine, the Tier-1
program at first failed to compile, because the standard networking headers pulled in a much larger
kernel header that the bundled compiler rejected outright. Diagnosing this required reading the compiler
output carefully enough to see that the failure lay in an unrelated header rather than in the program's
own logic. It was resolved by switching to the lighter user-facing (uapi) headers and by suppressing a
warning that a newer compiler had promoted to a fatal error — a change that altered no logic whatsoever
and left the maps, the behaviour, and the results untouched, but without which the system would not run
on that machine at all.

The second obstacle was a subtle testing artefact rather than a fault in the system. When the whole
evaluation was first attempted on a single machine over the loopback interface, a low threshold caused
the machine's own measurement traffic to cross the limit and be dropped, which silenced the dashboard
and produced confusing, empty readings. Recognising that the measurement channel itself was being
filtered by the very mechanism under test was an important realisation, and it led directly to the more
robust approach adopted in the evaluation: reading the kernel maps directly and generating traffic from
distinct, spoofed source addresses so that the measurement path stayed clear.

The third obstacle was a genuine design limitation in the machine-learning tier, and it is discussed
openly rather than hidden. The features the model was trained on were drawn from the dataset's rich,
per-flow records, whereas the features available at run time were the simpler per-source counts the
kernel maintains, so the two did not correspond as closely as they should. This did not affect the
kernel filtering, the adaptation, or the flash-crowd result, but it does mean the live classifier is
weaker than the offline accuracy figure alone would suggest, and for that reason addressing it is the
first item in the future work.

## 7.3 Self-reflection

### 7.3.1 Ideology about the research
My view of the work is that its value lies less in any single component than in the way the components
fit together to serve one clear purpose: stopping attacks without punishing real users. Over the course
of the project I came to believe strongly that a defence ought to be judged not only by what it blocks
but by what it wrongly blocks, and that measuring the second is as important as measuring the first. That
conviction is, in a sense, the intellectual core of the whole dissertation, and it is the lens through
which I would now approach any protective system.

### 7.3.2 Benefits gained
The most tangible benefit was learning to work at the kernel level with eBPF and XDP, a technology I had
not previously touched, and learning to reason carefully about the boundary between the fast kernel path
and the slower userspace path. I also gained practical experience of training and evaluating a model on a
recognised security dataset, and, more broadly, of building an end-to-end system in which many parts must
cooperate correctly, rather than an isolated script that does one thing. The habit of building and
verifying in small, testable steps is a benefit I expect to carry into future work.

### 7.3.3 Learning curves
The steepest learning curve was undoubtedly the eBPF verifier and the surrounding toolchain, where
problems could not always be anticipated and often had to be discovered by running the code and reading
the results. Debugging behaviour that spans the kernel and userspace at once was also new and demanding,
because the cause of a symptom in one world frequently lay in the other. Undertaking a system of this
kind with very little prior programming background was challenging throughout, and it was the iterative,
milestone-by-milestone method — proving each small piece before moving on — that made an otherwise
daunting project manageable.

## 7.4 Business Insight

### 7.4.1 Real-world application possibilities
The idea has clear and immediate practical relevance. Any service that experiences legitimate surges —
ticketing platforms, online retailers during sales, media sites during major events, or public-sector
portals at deadlines — faces exactly the problem this project targets: a defence that overreacts to a
spike can turn away the very customers that a surge represents, converting a moment of opportunity into a
moment of loss. A two-tier, flash-crowd-aware filter that runs cheaply on the host and escalates only
doubtful traffic could reduce both the impact of attacks and the revenue and reputation lost to wrongly
blocked users, addressing two costs that are usually treated separately. Because the approach uses
standard Linux facilities rather than specialised hardware, it is also comparatively inexpensive to
adopt, which lowers the barrier for smaller operators who cannot afford dedicated scrubbing
infrastructure. In commercial terms, the distinctive selling point is not merely that the system stops
attacks, but that it does so while protecting the customer experience during the busiest and most
valuable periods.

## 7.5 Future Recommendations

Several concrete steps would extend and strengthen the work. First, and most importantly, the
machine-learning tier should be retrained on features that can actually be computed at run time, so that
training and inference operate on the same representation; achieving this may require measuring a few
additional cheap per-source signals inside the kernel, which would also turn the current limitation into
a contribution about verifier-friendly feature design. Second, the evaluation should be repeated across
several machines or virtual machines to provide genuinely distinct users, with the live adaptive loop
choosing the threshold automatically and each scenario run several times so that the results can be
reported with a mean and a variance rather than as a single demonstration. Third, the comparison should
be broadened to include at least one prior published method as a baseline, not only a static threshold,
so that the system is positioned quantitatively against the state of the art. Beyond these, supporting
IPv6, examining application-layer surges, and studying the system's behaviour under a wider range of
attack patterns would broaden its reach and its evidential base. Taken together, these steps would move
the work from a convincing prototype towards a result strong enough for peer-reviewed publication, and
they define a clear and realistic path for anyone who wishes to continue it.
</content>
