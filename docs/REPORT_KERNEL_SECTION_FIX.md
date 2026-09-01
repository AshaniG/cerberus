# Fixing the interim report's kernel section to match the real implementation

Use this to update your interim report so its description of the kernel matches what
Cerberus actually does. Recommendation: keep the code as-is (it works and is proven);
edit the report text only.

## Replace in Section 1.8 (Rich Picture)

Old wording implied: decision tree compiled into the eBPF program (tail calls), per-flow
tracking of SYN/ACK ratio + packet-size variance, tree constants written into BPF maps.

Replacement paragraph (paste in place of the XDP-program description):

> The XDP program is attached to the network interface driver and receives every packet
> before the kernel constructs any further structures for it. For each IPv4 packet, the
> program performs a single, cheap operation: it increments a per-source-IP counter held
> in a BPF hash map and compares it against a threshold held in a separate BPF array map,
> not hard-coded into the program. If the counter has reached the threshold, the packet is
> dropped immediately with XDP_DROP; otherwise it is passed with XDP_PASS. This
> kernel-resident logic is deliberately minimal — a single arithmetic comparison per packet
> — so that it remains well within the eBPF verifier's bounded-computation limits. The
> machine-learning classifier is not compiled into the XDP program itself; it runs in
> userspace and is invoked only for sources whose counts fall within an ambiguous band, so
> that the expensive classification step never sits on the packet path.

## Add to Chapter 5 (Implementation) — honest design-decision note

> An earlier design considered compiling the decision-tree classifier directly into the
> eBPF program using tail calls, following Hara and Sasabe's approach. This was set aside
> in favour of a userspace classifier invoked selectively by the collector, since it
> achieves the same selective-escalation goal with substantially lower implementation risk
> within the project timeline, while keeping the kernel-resident logic simple enough to
> remain comfortably within the verifier's constraints.

## Dataset name — find & replace

Replace every occurrence of **"CICDDoS2019 and CICIoT2023"** with **"CIC-IDS-2017"** in:
- Section 1.9.2 (Software resources)
- Section 3.6.2 (Ethical Considerations)

The licensing/ethics claim (Canadian Institute for Cybersecurity, published, de-identified,
academic-use licence) stays true — CIC-IDS-2017 is from the same institute.

## Other small wording fixes (lower priority, same idea)

- Wherever the report says the map is keyed by **"flow"**, change to **"source IP"**
  (the real `ip_count` map key is just the source address, not a 5-tuple).
- Wherever the report promises **"separate counters per attack type"** (SYN/UDP/ICMP),
  either remove that claim or add a short note: *"the current prototype counts all IPv4
  traffic per source uniformly; per-protocol counters are noted as future work."*
- `flashcrowd_gen.py` uses a custom Python socket generator, not iperf3/wrk/tcpreplay —
  either update the tools list in 1.9.2 or add a footnote explaining the substitution.

## Why fix the report instead of the code

- The code already runs and produced a real result (12 legitimate users blocked with a
  static threshold vs 0 with the adaptive one) — that evidence is valuable and working.
- Compiling a decision tree into eBPF via tail calls is a genuine, hard research-engineering
  problem (the cited paper calls it a "significant engineering feat"). Attempting it now
  risks breaking a working system close to the deadline for a feature not required to
  answer the research question.
- A userspace Tier-2 classifier is a legitimate, common design — it still proves the same
  claim: adaptive threshold + selective escalation + flash-crowd false-positive reduction.
</content>
