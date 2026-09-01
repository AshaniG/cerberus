# Chapter 5 — Implementation

> **How to use this draft.** The code excerpts below are taken from your own repository and the
> execution evidence is from your real runs. Keep the snippets short in the final document (a few
> lines each), and make sure every piece of evidence — a dashboard screenshot, a terminal capture —
> is one you can reproduce and explain.

## 5.1 Building the Framework

The system was built from the bottom upwards, one runnable milestone at a time, so that every layer
was proven to work before the next was placed on top of it. The order was chosen deliberately rather
than for convenience. The riskiest and least predictable part of the whole undertaking was getting an
eBPF program to compile, pass the verifier, and attach to an interface on the specific machine
available; if that could not be made to work, nothing else would matter, and so it was tackled first.
Only once the toolchain was proven did the work move on to sharing state through a map, then to the
per-source counting and dropping that form the core of Tier 1, then to the userspace layers that read
and present that state, then to the adaptive control loop, then to the machine-learning tier, and
finally to the evaluation. Each step produced something that could be run and observed, which meant
that when a problem appeared it could be attributed to the small amount of new code rather than to a
large, undifferentiated mass. This section describes the logic of the parts that carry the
contribution, since the more routine layers follow standard practice.

### 5.1.1 Algorithms and Logic

**Tier-1 filtering (kernel).** The heart of the system is small enough to be stated as pseudocode. For
every packet, the program performs a strictly bounded amount of work and returns a verdict:

```
on packet:
    if ethernet/IPv4 headers not fully in bounds: return PASS
    if not IPv4: return PASS
    increment totals[seen]
    src ← source IP
    count ← ip_count[src] + 1        # the packet is counted even if it will be dropped
    threshold ← config[0]  (default 250 if unset)
    if count ≥ threshold:
        increment totals[dropped]; return DROP
    else:
        increment totals[passed]; return PASS
```

Two properties of this algorithm matter beyond its obvious function. The first is that the amount of
work per packet is constant and contains no unbounded loop, which is exactly what allows the eBPF
verifier to accept the program; a design that required, say, iterating over a variable-length list
would be rejected, and this constraint is the reason the whole system is arranged so that expensive
reasoning happens elsewhere. The second is that the threshold is not a compiled-in constant but is
read from a map on every single packet. That one design decision is what makes the threshold a live,
externally controllable value and therefore what makes reload-free adaptation possible at all.

**Adaptive control (userspace).** The control loop is the component that turns recent traffic into a
new threshold. It measures the global packet rate between successive ticks, smooths that rate with an
exponentially weighted moving average so that a single momentary spike does not swing the threshold
violently, and then sets the threshold to sit above the typical level by a configurable margin,
clamped to a sensible minimum and maximum so that it can never become absurdly small or large:

```
each interval (adaptive enabled):
    rate ← (seen_now − seen_prev) / elapsed
    ewma ← α·rate + (1 − α)·ewma
    candidate ← clamp( max(ewma · interval, top_source · 0.5) · margin, min, max )
    if candidate differs meaningfully from the current threshold:
        write candidate into config[0]      # the kernel sees it on the next packet
```

The use of a moving average rather than the instantaneous rate is a deliberate choice: it gives the
threshold a short memory, so that it rises smoothly to accommodate a developing surge rather than
reacting to every fluctuation, which is the behaviour needed to spare a flash crowd without ignoring a
genuine attack. The final guard — only writing when the new value differs meaningfully from the
current one — avoids needless churn in the map and needless entries in the event log.

**Selective escalation (userspace).** Rather than run the classifier on every source, which would
reintroduce exactly the cost the design is trying to avoid, the collector escalates only those sources
whose counts fall within an ambiguous band between a soft fraction of the threshold and the threshold
itself. Only those sources are passed to the decision tree:

```
for each top source:
    if count ≥ threshold and it was previously below: record a DROP event
    else if soft ≤ count < threshold and it was previously below soft:
        record an ESCALATE event
        label ← classify(source features)      # the Tier-2 decision tree
        record an ML event(label)
```

This is the concrete expression of the "filter cheaply, escalate selectively" principle. Sources that
are clearly benign never trigger anything, sources that are clearly attacking are dropped by Tier 1
without ever reaching the tree, and only the genuinely doubtful minority incur the cost of
classification.

> *(Insert Figure 5.1 — a block-diagram series showing: packet → Tier-1 filter → maps → collector →
> (ambiguous?) → Tier-2 tree, with the control loop writing the threshold back into the maps.)*

### 5.1.3 Justification of Technologies

The technology choices were driven throughout by the constraints of the problem and by a consistent
preference for simple, well-understood tools over more powerful but more complex alternatives.

| Layer | Technology chosen | Why it was chosen |
|---|---|---|
| Tier-1 program | eBPF in restricted C | The only way to run code at the XDP hook; runs as verified bytecode at the earliest, fastest point in the networking path. |
| eBPF toolchain | BCC (with Python bindings) | Compiles the C on the host at load time, which avoids kernel-header mismatch problems and gives a fast edit–run–observe cycle well suited to a first eBPF project. |
| Userspace services | Python 3 | Simple and clear; because these run only a few times per second and off the packet path, their execution speed is irrelevant to forwarding performance. |
| Tier-2 model | scikit-learn decision tree | Once trained, it reduces to a short, bounded sequence of comparisons — fast to evaluate and far more appropriate here than a deep neural network, which the verifier constraints and the project scope both rule out. |
| Data handling | pandas, NumPy | The standard tools for loading the CIC-IDS-2017 CSV files and projecting them into the feature vector used for training. |
| Storage | SQLite | File-based, reproducible, and requiring no separate server, which makes it ideal for an offline, examinable research project. |
| API and dashboard | FastAPI with HTML, CSS, JavaScript, and Chart.js | Provides a genuine REST API and a light front end with no heavy build step, keeping the demonstration finishable within the available time. |
| Traffic generation | hping3 with a custom Python generator | hping3 is a standard tool for crafted flood traffic, complemented by a custom generator for the legitimate-surge scenario. |

## 5.2 Significant Implementation Attempts (with evidence)

This section presents the implementation attempts that carry the contribution, each paired with the
evidence that it works. Routine functionality is omitted in favour of the parts that embody the novel
logic.

**The kernel drop decision.** The core of Tier 1 is the handful of lines that read the live threshold
from the map, compare it against the source's count, and drop or pass accordingly:

```c
u64 *thr_ptr = config.lookup(&cfg_key);
u64 threshold = thr_ptr ? *thr_ptr : 250;
if (count >= threshold) {
    bump_total(1);            /* packets_dropped */
    return XDP_DROP;
}
bump_total(2);               /* packets_passed */
return XDP_PASS;
```

*Evidence.* With the program attached and a flood fired from a single source against a high threshold,
the kernel counters, read directly from the maps, showed on the order of 1.86 million packets seen and
1.66 million dropped from the attacking source, while a separate low-volume source was passed
untouched. This confirms requirement F2 — dropping over the threshold — on real traffic and at
substantial volume, and it demonstrates that the drop decision is genuinely per-source rather than
global, since the quiet source was unaffected while the noisy one was blocked.

**The live threshold update.** The adaptive contribution depends on userspace being able to change the
threshold in the running kernel program, which the control loop achieves by writing into the map
through the session:

```python
self.session.set_threshold(candidate)
# BpfSession.set_threshold  ->  self.b["config"][0] = c_uint64(candidate)
```

*Evidence.* Setting the threshold through the API and then observing that the very next packets were
treated according to the new value, with no reload of the kernel program and no interruption to
forwarding, confirms requirement F3 — a runtime threshold change without a reload. This is the
mechanism on which the entire adaptive design rests, and demonstrating it directly is therefore
important.

**Selective escalation and the machine-learning verdict.** When a source enters the ambiguous band, the
collector escalates it and records the classifier's answer:

```python
label, score = classify_flow({"packet_count": count, "threshold": thr, "src_ip": ip})
db.insert_event(self.conn, "ml", ip, f"ml_label={label} score={score:.3f} count={count}")
```

*Evidence.* During a run, the event log showed an ambiguous source being escalated and then labelled by
the tree — for example, an escalate event for a source at 722 packets, immediately followed by a
machine-learning event reading `ml_label=attack`. Crucially, obvious attackers were dropped by Tier 1
without ever generating a classification event, while only sources in the ambiguous band were passed to
the tree. This confirms requirement F5 and, more importantly, demonstrates the selective character of
the design in operation: the expensive tier really is reserved for the doubtful minority.

**Training the tree on real data.** The decision tree was trained on the CIC-IDS-2017 CSV files,
projected into a small feature vector, and saved to disk for the live path to load on demand.

*Evidence.* Training on 702,718 real labelled samples produced a decision tree with an overall accuracy
of 0.86, with the full per-class precision and recall reported in Chapter 6. That the accuracy is a
realistic figure rather than a perfect one is itself evidence that the model was trained and evaluated
on genuine, messy, real-world data rather than on an artificially separable synthetic set, which
strengthens rather than weakens the credibility of the result.

> *(Insert Figure 5.2 — a screenshot of the live dashboard during an attack, showing Tier-1 ON, the
> attacking source highlighted in red with the action "drop", and the Seen and Dropped counters
> rising.)*

## 5.3 Chapter Summary

This chapter described how the two-tier design was implemented and gave evidence that the parts carrying
the contribution work on real traffic. It set out the bounded per-packet filtering algorithm and
explained why its boundedness is what allows it to run in the kernel at all; it presented the
exponentially weighted adaptive control loop and the reasoning behind smoothing the rate; and it
described the selective escalation logic that reserves the classifier for the ambiguous minority. It
justified each technology choice against the constraints of the project, and it showed, with real code
and real execution evidence, that the kernel drops over a live threshold, that the threshold can be
changed without a reload, that only ambiguous sources are escalated to the tree, and that the tree was
trained on the real CIC-IDS-2017 dataset. With the system built and its individual behaviours
demonstrated, the next chapter evaluates it as a whole against the research question.
</content>
