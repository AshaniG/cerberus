# CHAPTER 7 - CONCLUDING REMARKS

## 7.1 Accomplishment of the Research Objectives

Each of the four objectives set out in Section 1.7 was met, and it is worth checking each
against the evidence gathered in Chapters Five and Six rather than simply asserting that
it was.

The first objective, to identify the limitations of existing eBPF/XDP approaches and the
gap around testing against legitimate traffic surges, was met through the literature
review in Chapter Two and reinforced by direct experience of the eBPF verifier's limits
during development - reading about the verifier's constraints and actually running into
them, for instance while getting the very first kernel program to compile on the
development machine, are not the same thing, and the second was far more instructive than
the first. The second objective, to analyse the trade-off between a statistical
pre-filter and a compiled machine-learning approach under the verifier's constraints, was
addressed in Section 2.5 and confirmed in practice by the decision, discussed in Chapter
Five, to keep the classifier in userspace rather than compiling it into the kernel
program, following the same reasoning SmartX Intelligent Sec gives for the same choice.
The third objective, to design and develop a working prototype combining these ideas, was
met concretely: the system attaches, counts, drops, adapts its threshold live, and
escalates selectively, each demonstrated with real evidence in Chapter Five. The fourth
objective, to evaluate the prototype against both attack and flash-crowd traffic, produced
the central result of the whole dissertation - a static threshold that blocked twelve out
of twelve legitimate sources, against an adaptive threshold that blocked none, with both
configurations catching the attacker fully.

Putting the three independent strands of evidence side by side - the functional
tests confirming the mechanism works, the 0.86 accuracy of the classifier on a real
benchmark dataset, and the flash-crowd comparison itself - the research question posed in
Chapter One can be answered with a qualified yes: this design does maintain attack
detection while measurably reducing flash-crowd false positives relative to a static
baseline, at least under the conditions tested so far, with the honestly-stated
limitations set out in Section 6.5.

## 7.2 Problems Encountered

Three problems shaped this project in ways worth recording, because each one changed a
real decision rather than being a minor inconvenience.

The first was environmental rather than conceptual. The Tier-1 program, in its original
form, would not compile on the development machine's particular kernel, failing with a
compiler error buried inside an unrelated system header pulled in through the standard
networking headers. Tracking this down took real time and involved reading compiler
output far more carefully than expected, before the actual, small fix - switching to
lighter headers and suppressing one warning - became obvious. Nothing about the program's
logic changed; the fix was purely one of portability, but finding it was not obvious in
advance.

The second was a measurement problem rather than an implementation one. An early attempt
to read results back through the system's own dashboard produced numbers that made no
sense, because the dashboard's own polling traffic was itself subject to the filtering
being tested, and a low threshold silenced the very API being used to observe the system.
Recognising this - that a defence mechanism can interfere with the tool measuring it -
led straight to reading the kernel maps with bpftool instead, which removed the problem.

The third was a real limitation in the machine-learning tier, and one that is
acknowledged rather than hidden: the features used at inference time, drawn from what the
kernel maps can cheaply provide, are a simplified approximation of the richer flow-level
features CIC-IDS-2017 itself contains. This does not affect the kernel filtering, the
threshold adaptation, or the flash-crowd result, but it does mean the classifier's
real-world accuracy is likely somewhat lower than the 0.86 figure measured offline
suggests, and closing this gap is the first item in the future work discussed below.

## 7.3 Self-reflection

### 7.3.1 Ideology About the Research Carried Out

Working through this project changed how the researcher thinks about what makes a DDoS
defence good. Before starting, "good" meant catching attacks. By the end, it meant
something narrower and, in this researcher's view, more honest: catching attacks without
quietly punishing the people the system exists to protect in the first place. A defence
that blocks everything technically has perfect detection and is also useless, and it was
only by building and measuring the flash-crowd scenario first-hand that this stopped
being an abstract point from the literature review and became something demonstrated with
real numbers.

### 7.3.2 Benefits Gained

The clearest benefit was hands-on experience with eBPF and XDP, a technology this
researcher had not touched before starting, and with reasoning carefully about the
boundary between a fast, constrained kernel path and a slower, flexible userspace path.
A second, less expected benefit was learning to train and honestly evaluate a
machine-learning model against a recognised security benchmark, including learning to be
suspicious of results that look too good, rather than simply reporting the highest
accuracy figure obtained.

### 7.3.3 Learning Curves

The steepest part of the learning curve was the eBPF verifier itself and the surrounding
toolchain, where the same code could behave differently on a different kernel version,
and where problems generally had to be found by running the code rather than by reading
documentation in advance. Debugging behaviour that spans the kernel and userspace boundary
was demanding in a way that debugging a single Python script never is, since the cause of
an odd symptom in one half was often sitting in the other. Undertaking a project of this
technical depth with limited prior systems-programming experience was honestly
challenging throughout, and the decision, explained in Chapter Three, to work in small,
individually-tested milestones rather than attempting the whole system at once is what
made that challenge manageable rather than overwhelming.

## 7.4 Business Insight of Your Idea

### 7.4.1 Real-world Application Possibilities

The problem this dissertation addresses is not a niche one. Any service that experiences
legitimate demand surges - a ticket release, a retail sale, breaking news traffic, a
public-sector portal on a deadline day - faces exactly the trade-off studied here: a
defence tuned aggressively enough to stop an attack can just as easily turn away the
customers a surge represents, converting a moment of opportunity into a moment of lost
business. A host-level, flash-crowd-aware filter of the kind built here could reduce both
the damage caused by real attacks and the quieter, harder-to-notice cost of wrongly
blocked legitimate users, using only standard Linux facilities rather than specialised or
expensive hardware. That makes the underlying idea realistically adoptable by smaller
organisations that could never afford enterprise-grade scrubbing services in the first
place, which is precisely the gap identified as motivation in Section 1.5.

## 7.5 Future Recommendations

Several concrete extensions follow naturally from the limitations acknowledged above.
Retraining the classifier on features that can actually be measured at inference time,
rather than on the richer offline dataset features it currently learns from, would close
the gap between the reported 0.86 accuracy and the classifier's real behaviour in
production, and is the most important of these. Repeating the flash-crowd evaluation
across truly separate physical machines, with the adaptive control loop choosing its
own threshold during the run rather than a fixed stand-in value, and running each scenario
several times to report a mean and a spread, would turn the current demonstration into a
fuller statistical result. Extending the comparison to include at least one previously
published method as a second baseline, rather than only a static threshold, would allow
the system to be positioned quantitatively against the state of the art rather than only
against a strawman. Beyond these, supporting IPv6 traffic and examining
application-layer surges, both explicitly out of scope in Chapter One, would broaden the
system considerably. Between them, these steps mark a realistic path from a working,
evidenced prototype towards a result solid enough to submit for peer review.
