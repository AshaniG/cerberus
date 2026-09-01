# CHAPTER 5 - IMPLEMENTATION / DESIGNING

## 5.1 Building the Framework

The system was built from the bottom up, milestone by milestone, in the order set out in
the timeline in Section 3.6.1. This order was not arbitrary. Because eBPF's behaviour on
a given machine cannot always be predicted in advance - whether a program compiles,
whether the verifier accepts it, whether native XDP mode is even available on a given
interface - the single biggest risk in the whole project was discovering, late, that the
toolchain simply would not cooperate on the machine available. For that reason, the very
first milestone was the smallest possible eBPF program: one that attaches at the XDP hook
and does nothing but pass every packet through untouched, purely to prove that BCC could
compile a program, the verifier would accept it, and the interface would take an XDP
attachment at all. Only once that was working did the project move on to a global packet
counter, then to per-source counting with thresholded dropping, then to the userspace
layers that read and act on that state, then to the adaptive control loop, then to the
machine-learning tier, and finally to evaluation. Each step produced something that could
actually be run and watched before the next one began.

### 5.1.1 Algorithm and Logic

The logic that matters most in this dissertation is small enough to state precisely. The
Tier-1 filtering decision, which runs once per packet inside the kernel, is this:

```
on packet arrival:
    if the Ethernet header does not fit within the packet: PASS
    if the packet is not IPv4: PASS
    if the IPv4 header does not fit within the packet: PASS
    increment the global "seen" counter
    src <- source IP address
    count <- ip_count[src] + 1
    threshold <- config[0]   (250 if nothing has been written yet)
    if count >= threshold:
        increment the global "dropped" counter
        return XDP_DROP
    else:
        increment the global "passed" counter
        return XDP_PASS
```

Two things about this deserve comment, because they were not accidental. First, the
amount of work per packet is fixed and small - a couple of map lookups and one
comparison - which is exactly what lets the eBPF verifier accept the program in the first
place; there is no loop here that could run for an unpredictable number of iterations.
Second, the threshold is read from a map on every single packet rather than compiled in
as a constant, which is the one design decision the entire adaptive-threshold contribution
rests on.

The adaptive control loop, running in userspace on a two-second timer, turns recent
traffic into a new threshold like this:

```
each tick, while adaptive mode is enabled:
    rate <- (packets seen now - packets seen last tick) / seconds elapsed
    smoothed_rate <- 0.3 * rate + 0.7 * smoothed_rate   (exponential moving average)
    candidate <- clamp( max(smoothed_rate * interval, top_source_count * 0.5) * 1.5,
                         minimum 50, maximum 5000 )
    if candidate differs meaningfully from the current threshold:
        write candidate into config[0]
```

The exponential moving average was chosen deliberately over using the instantaneous rate
directly, because a single momentary spike - a handful of packets arriving close
together, which happens constantly even on quiet traffic - would otherwise cause the
threshold to jump around far more than is useful. Smoothing gives the threshold a short
memory, so it climbs steadily during a genuine surge instead of over-reacting to noise.

The selective escalation logic, also running in the collector on its own tick, decides
which sources are worth the cost of classification:

```
for each of the top sources read from the maps this tick:
    if count >= threshold and it was not over threshold last tick:
        record a "drop" event
    else if soft_band <= count < threshold and it was not in the soft band last tick:
        record an "escalate" event
        label, score <- classify(count, threshold)
        record an "ml" event with that label and score
```

where `soft_band` is set at sixty percent of the current threshold. Sources well below
this band are left alone entirely, and sources already over the hard threshold are simply
dropped by Tier 1 without ever reaching the classifier - only the narrow band in between
is ever escalated, which is what keeps the classifier's cost off the packet path.

### 5.1.3 Justification of Technologies

| Layer | Technology | Reason it was chosen |
|---|---|---|
| Tier-1 program | eBPF, written in restricted C | The only language the XDP hook accepts; runs as verified bytecode at the earliest point in the networking path. |
| eBPF toolchain | BCC | Compiles the C source on the host at load time, avoiding the kernel-header version mismatches that make libbpf-based workflows harder to get started with on a new machine. |
| Userspace services | Python 3 | These run a handful of times per second, well off the packet path, so clarity mattered far more here than raw execution speed. |
| Tier-2 classifier | scikit-learn decision tree | Compiles down to a short, bounded sequence of comparisons at inference time, which fits the "cheap enough to run selectively" requirement, and is far easier to train, inspect, and reason about than a neural network. |
| Data handling | pandas, NumPy | Standard tools for loading and projecting the CIC-IDS-2017 CSV files into a training set. |
| Storage | SQLite locally, MongoDB Atlas as a mirror | SQLite needs no separate server and is trivially reproducible for offline testing; the MongoDB mirror was added so live event and snapshot data could also be inspected from outside the host, without making the whole system depend on network access to function. |
| API and dashboard | FastAPI, with HTML/CSS/JavaScript and Chart.js | Gives a genuine REST API with a lightweight front end and no build step, which kept the demonstration side of the project achievable inside the available time. |
| Traffic generation | hping3, plus a custom Python generator | hping3 is a well-established tool for crafted flood traffic; the flash-crowd side needed a generator capable of simulating many distinct, modest-rate sources, which no single off-the-shelf tool did cleanly, so a small Python script using threaded socket connections was written instead. |

## 5.2 Significant Implementation Attempts

This section covers the parts of the implementation that carry the dissertation's actual
contribution, each shown with the evidence that it works, rather than routine plumbing
code.

**Getting the kernel program to compile at all.** The first real obstacle was not
conceptual but environmental. On the development machine's particular kernel, the
original version of the Tier-1 program, which included the standard `<linux/if_ether.h>`
and `<linux/ip.h>` headers, failed to compile: the compiler reported a `static_assert`
failure buried inside `<linux/fs.h>`, a header pulled in indirectly through the networking
headers and unrelated to anything the program itself does. The fix was to switch to the
lighter, user-facing `<uapi/linux/if_ether.h>` and `<uapi/linux/ip.h>` headers, which
define the same `struct ethhdr` and `struct iphdr` without pulling in the problematic
chain, and to add a single compiler flag suppressing a warning that a newer compiler
version had turned into a hard error. Neither change touches the program's logic, its
maps, or its behaviour in any way; both are portability fixes, and the program was
verified to still compile, load, attach, and correctly update its counters afterwards.
This is a small detail in the code, but it is worth including here because it is exactly
the kind of practical obstacle that eBPF development involves and that no amount of
reading about the technology in advance prepares a student for.

**The kernel drop decision, under real load.** With the program attached and a flood of
roughly 1.86 million packets sent from a single spoofed source against a threshold of
200,000, the kernel's own counters - read directly from the `totals` map, not through the
dashboard - showed 1,856,935 packets seen, 1,656,847 dropped, and 200,088 passed. A second,
low-volume source sending ordinary traffic over the same period was left completely
untouched, confirming that the drop decision is genuinely per-source rather than global.
This is the clearest possible demonstration of requirement F2 from Chapter Four.

**The live threshold update.** To confirm that the threshold can change without a reload,
the value was updated through the API while the program remained attached and traffic
continued to flow; the very next packets were judged against the new value, with no
interruption to forwarding and no re-attachment of the program. This is the mechanism the
entire adaptive-threshold contribution depends on, and it was verified directly rather
than assumed.

**A subtlety discovered during measurement.** An early attempt to measure the system by
polling its own dashboard while a low threshold was in effect produced results that made
no sense - the counters appeared to freeze. The cause turned out to be that the
dashboard's own polling traffic, arriving from the same host, was itself being counted
and eventually blocked by the very threshold being tested, which silenced the API that was
supposed to be reporting on it. Once this was understood, the evaluation approach was
changed to read the BPF maps directly with bpftool, bypassing the dashboard entirely for
measurement purposes, which removed the problem completely. This is recorded here, and
again in Chapter Seven, because it is a genuine methodological lesson rather than
something to gloss over: a defence mechanism can interfere with the tool being used to
observe it, and that has to be designed around rather than discovered by accident during
a live demonstration.

**Selective escalation and the classifier's verdict.** During a run with one source held
in the ambiguous band, the event log recorded an `escalate` event for that source at 722
packets against a threshold of 1,000, immediately followed by an `ml` event reading
`ml_label=attack score=1.000`. Sources that were obviously over threshold generated `drop`
events without ever appearing in an `escalate` or `ml` event at all, which is the
behaviour F5 requires: the classifier genuinely is only reached by the ambiguous minority.

**Training on real data.** The decision tree was trained on the eight CIC-IDS-2017 CSV
files, projected down to a small feature vector built from packet count, the ratio of
that count to the threshold, an approximate byte rate, an approximate SYN ratio, and flow
duration. Training on 702,718 real, labelled samples produced a model with an overall
accuracy of 0.86, reported in full in Chapter Six. This is the concrete evidence that the
machine-learning tier was trained and evaluated against a genuine benchmark dataset, not
one shaped to make the numbers look better than they are.

During a live attack run, the dashboard reflected this directly: Tier-1 showed as
attached and live, the attacking source was highlighted with the action "drop," and the
Seen and Dropped counters climbed in step with the flood being generated.

## 5.3 Chapter Summary

This chapter described how the two-tier design from Chapter Four was actually built. It
set out the bounded per-packet filtering logic and explained why its boundedness is what
allows it to run inside the kernel at all, the exponentially-smoothed adaptive control
loop, and the selective-escalation rule that keeps the classifier off the packet path. It
justified each technology choice against the practical constraints of the project, and it
gave real evidence - a portability fix that was needed before the kernel program would
even compile, live packet counts read directly from the kernel during a flood, a
confirmed live threshold change, a genuine measurement pitfall that was found and worked
around, and a classifier trained on 702,718 real samples - that the system does what
Chapter Four specified. Chapter Six now turns to testing this system formally and
evaluating it against the research question.
</content>
