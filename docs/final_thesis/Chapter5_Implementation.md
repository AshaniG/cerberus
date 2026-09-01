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

The logic that matters most in this dissertation is small enough to show verbatim, rather
than paraphrase. The Tier-1 filtering decision, which runs once per packet inside the
kernel, is the closing section of `kernel/xdp_ddos.c`:

```c
int xdp_ddos(struct xdp_md *ctx)
{
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;

    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return XDP_PASS;

    struct iphdr *iph = (void *)(eth + 1);
    if ((void *)(iph + 1) > data_end)
        return XDP_PASS;

    bump_total(0); /* packets_seen */

    u32 src = iph->saddr;
    u64 zero = 0;
    u64 *cnt = ip_count.lookup_or_init(&src, &zero);
    if (!cnt)
        return XDP_PASS;

    __sync_fetch_and_add(cnt, 1);
    u64 count = *cnt;

    u32 cfg_key = 0;
    u64 *thr_ptr = config.lookup(&cfg_key);
    u64 threshold = thr_ptr ? *thr_ptr : 250;

    if (count >= threshold) {
        bump_total(1); /* packets_dropped */
        return XDP_DROP;
    }

    bump_total(2); /* packets_passed */
    return XDP_PASS;
}
```

The full listing, including the map declarations and the `bump_total` helper above this
function, is given in Appendix A. Two things about this function deserve comment, because
they were not accidental. First, the amount of work per packet is fixed and small - two
map lookups and one comparison - which is exactly what lets the eBPF verifier accept the
program in the first place; there is no loop here that could run for an unpredictable
number of iterations. Second, `config.lookup(&cfg_key)` reads the threshold from a map on
every single packet rather than the value being compiled in as a constant, which is the
one line the entire adaptive-threshold contribution rests on.

The adaptive control loop, running in userspace on a two-second timer, turns recent
traffic into a new threshold. This is the relevant part of `backend/control_loop.py`:

```python
def tick(self) -> None:
    totals = self.session.read_totals()
    now = time.time()
    seen = totals["seen"]

    if self._prev_seen is None or self._prev_ts is None:
        self._prev_seen = seen
        self._prev_ts = now
        return

    dt = max(now - self._prev_ts, 1e-3)
    rate = (seen - self._prev_seen) / dt  # packets per second (global)
    self._prev_seen = seen
    self._prev_ts = now

    if self._ewma_rate is None:
        self._ewma_rate = rate
    else:
        a = self.ewma_alpha
        self._ewma_rate = a * rate + (1 - a) * self._ewma_rate

    top = self.session.top_ips(5)
    top_count = top[0]["count"] if top else 0
    baseline = max(self._ewma_rate * self.interval, 1.0)
    candidate = int(max(baseline, top_count * 0.5) * self.margin)
    candidate = max(self.min_threshold, min(self.max_threshold, candidate))

    current = self.session.get_threshold()
    if abs(candidate - current) < max(5, int(current * 0.05)):
        return

    self.session.set_threshold(candidate)
```

The exponential moving average (`self._ewma_rate`) was chosen over using the raw
instantaneous rate on its own, because a single momentary spike - a handful of packets
arriving close together, which happens constantly even on quiet traffic - would otherwise
cause the threshold to jump around far more than is useful. Smoothing gives the threshold
a short memory, so it climbs steadily during a real surge instead of over-reacting to
noise. The final `self.session.set_threshold(candidate)` call is what writes the new value
into the `config` BPF map shown in the kernel listing above - this single call is the
entire mechanism behind Chapter One's claim of adaptation with no reload.

The selective escalation logic, running in the collector on its own one-second tick,
decides which sources are worth the cost of classification. This is the relevant part of
`backend/collector.py`:

```python
for row in top:
    ip = row["ip"]
    count = row["count"]
    prev = self._prev_dropped.get(ip, 0)
    if count >= thr and prev < thr:
        detail = f"count={count} threshold={thr}"
        db.insert_event(self.conn, "drop", ip, detail)
    elif soft <= count < thr and prev < soft:
        # Ambiguous band -- escalate for Tier-2 ML (M5).
        detail = f"ambiguous count={count} soft={soft} hard={thr}"
        db.insert_event(self.conn, "escalate", ip, detail)
        self._try_classify(ip, count, thr)
    self._prev_dropped[ip] = count
```

where `soft` is set earlier in the same method as `int(thr * self.soft_ratio)`, with
`soft_ratio` defaulting to 0.6 - sixty percent of the current threshold. Sources well
below this band are left alone entirely, and sources already over the hard threshold are
simply dropped by Tier 1 without ever reaching `_try_classify`, which is the method that
actually calls the decision tree - only the narrow band in between is ever escalated,
which is what keeps the classifier's cost off the packet path.

### 5.1.3 Justification of Technologies

| Layer | Technology | Reason it was chosen |
|---|---|---|
| Tier-1 program | eBPF, written in restricted C | The only language the XDP hook accepts; runs as verified bytecode at the earliest point in the networking path. |
| eBPF toolchain | BCC | Compiles the C source on the host at load time, avoiding the kernel-header version mismatches that make libbpf-based workflows harder to get started with on a new machine. |
| Userspace services | Python 3 | These run a handful of times per second, well off the packet path, so clarity mattered far more here than raw execution speed. |
| Tier-2 classifier | scikit-learn decision tree | Compiles down to a short, bounded sequence of comparisons at inference time, which fits the "cheap enough to run selectively" requirement, and is far easier to train, inspect, and reason about than a neural network. |
| Data handling | pandas, NumPy | Standard tools for loading and projecting the CIC-IDS-2017 CSV files into a training set. |
| Storage | SQLite locally, MongoDB Atlas as a mirror | SQLite needs no separate server and is trivially reproducible for offline testing; the MongoDB mirror was added so live event and snapshot data could also be inspected from outside the host, without making the whole system depend on network access to function. |
| API and dashboard | FastAPI, with HTML/CSS/JavaScript and Chart.js | Gives a proper REST API with a lightweight front end and no build step, which kept the demonstration side of the project achievable inside the available time. |
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
200,000, the kernel's own counters - read straight from the `totals` map, not through the
dashboard - showed 1,856,935 packets seen, 1,656,847 dropped, and 200,088 passed. A second,
low-volume source sending ordinary traffic over the same period was left completely
untouched, confirming that the drop decision is applied per source rather than globally.
This is the clearest possible demonstration of requirement F2 from Chapter Four.

**The live threshold update.** To confirm that the threshold can change without a reload,
the value was updated through the API while the program remained attached and traffic
continued to flow; the very next packets were judged against the new value, with no
interruption to forwarding and no re-attachment of the program. This is the mechanism the
entire adaptive-threshold contribution depends on, and it was confirmed by observation
rather than assumed.

**A subtlety discovered during measurement.** An early attempt to measure the system by
polling its own dashboard while a low threshold was in effect produced results that made
no sense - the counters appeared to freeze. The cause turned out to be that the
dashboard's own polling traffic, arriving from the same host, was itself being counted
and eventually blocked by the very threshold being tested, which silenced the API that was
supposed to be reporting on it. Once this was understood, the evaluation approach was
changed to read the BPF maps with bpftool instead, bypassing the dashboard entirely for
measurement purposes, which removed the problem completely. This is recorded here, and
again in Chapter Seven, because it is an honest methodological lesson rather than
something to gloss over: a defence mechanism can interfere with the tool being used to
observe it, and that has to be designed around rather than discovered by accident during
a live demonstration.

**Selective escalation and the classifier's verdict.** During a run with one source held
in the ambiguous band, the event log recorded an `escalate` event for that source at 722
packets against a threshold of 1,000, immediately followed by an `ml` event reading
`ml_label=attack score=1.000`. Sources that were obviously over threshold generated `drop`
events without ever appearing in an `escalate` or `ml` event at all, which is the
behaviour F5 requires: the classifier truly is only reached by the ambiguous minority.

**Training on real data.** The decision tree was trained on the eight CIC-IDS-2017 CSV
files, projected down to a small feature vector built from packet count, the ratio of
that count to the threshold, an approximate byte rate, an approximate SYN ratio, and flow
duration. Training on 702,718 real, labelled samples produced a model with an overall
accuracy of 0.86, reported in full in Chapter Six. This is the concrete evidence that the
machine-learning tier was trained and evaluated against an actual benchmark dataset, not
one shaped to make the numbers look better than they are.

During a live attack run, the dashboard showed this clearly: Tier-1 appeared as
attached and live, the attacking source was highlighted with the action "drop," and the
Seen and Dropped counters climbed in step with the flood being generated.

## 5.3 Chapter Summary

This chapter described how the two-tier design from Chapter Four was actually built. It
set out the bounded per-packet filtering logic and explained why its boundedness is what
allows it to run inside the kernel at all, the exponentially-smoothed adaptive control
loop, and the selective-escalation rule that keeps the classifier off the packet path. It
justified each technology choice against the practical constraints of the project, and it
gave real evidence - a portability fix that was needed before the kernel program would
even compile, live packet counts read straight from the kernel during a flood, a
confirmed live threshold change, a genuine measurement pitfall that was found and worked
around, and a classifier trained on 702,718 real samples - that the system does what
Chapter Four specified. Chapter Six now turns to testing this system formally and
evaluating it against the research question.
</content>
