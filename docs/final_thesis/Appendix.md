# APPENDIX

## Appendix A: Tier-1 Kernel Source Listing

The listing below is the complete source of `kernel/xdp_ddos.c`, the eBPF/XDP program
that implements Tier 1 of the system, referenced throughout Chapters 4 and 5.

```c
/*
 * xdp_ddos.c - Milestone M2+: Tier 1 DDoS filter at the XDP hook.
 *
 * For every IPv4 packet:
 *   1. Parse the Ethernet + IPv4 headers to get the source IP.
 *   2. Increment that IP's counter in the ip_count hash map.
 *   3. Compare against the live threshold in config map (key 0).
 *   4. XDP_DROP if over threshold; otherwise XDP_PASS.
 *
 * MAP CONTRACT (shared with the collector and the control loop)
 *   ip_count : BPF_HASH  key=u32 (IPv4 src, network byte order), value=u64
 *   config   : BPF_ARRAY key=u32 index 0 -> threshold (u64 packets)
 *   totals   : BPF_ARRAY key=u32  0=packets_seen  1=packets_dropped  2=packets_passed
 */

#include <uapi/linux/if_ether.h>
#include <uapi/linux/ip.h>

/* Per-source-IP packet counters. Max entries keeps map memory bounded. */
BPF_HASH(ip_count, u32, u64, 10240);

/* config[0] = drop threshold. Userspace writes a new value here for live
   adaptive updates, without reloading this program. */
BPF_ARRAY(config, u64, 1);

/* Global tallies for the dashboard: seen / dropped / passed. */
BPF_ARRAY(totals, u64, 3);

static __always_inline void bump_total(u32 idx)
{
    u64 *v;
    u64 zero = 0;

    v = totals.lookup_or_init(&idx, &zero);
    if (v)
        __sync_fetch_and_add(v, 1);
}

int xdp_ddos(struct xdp_md *ctx)
{
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    struct ethhdr *eth = data;
    /* Verifier requires every pointer arithmetic to be bounds-checked. */
    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;

    /* Only IPv4; IPv6 / ARP / etc. pass through untouched. */
    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return XDP_PASS;

    struct iphdr *iph = (void *)(eth + 1);
    if ((void *)(iph + 1) > data_end)
        return XDP_PASS;

    bump_total(0); /* packets_seen */

    u32 src = iph->saddr; /* already network byte order - use as map key */
    u64 zero = 0;
    u64 *cnt = ip_count.lookup_or_init(&src, &zero);
    if (!cnt)
        return XDP_PASS;

    __sync_fetch_and_add(cnt, 1);
    u64 count = *cnt;

    /* Default threshold if userspace has not written config[0] yet. */
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

## Appendix B: Additional Test Cases

These cases extend Section 6.2 and include cases that surfaced real issues during
development, which were then fixed - included here because they say as much about the
system's robustness as the cases that simply passed.

| ID | Test Case | Expected Result | Outcome |
|---|---|---|---|
| F-09 | Clear counters through the dashboard while the program is attached | `ip_count` and `totals` reset to zero; a `clear` event is recorded | Pass |
| F-10 | Toggle adaptive mode off, then back on | Threshold stops changing automatically while off; the control loop resumes computing and writing a new threshold once re-enabled | Pass |
| F-11 | Attach the XDP program on a non-standard, newer kernel version | Initial attempt failed to compile against the full `linux/if_ether.h` / `linux/ip.h` headers on this kernel; switching to the lightweight `uapi` headers and adding a compiler flag resolved it without changing any detection logic | Pass (after fix) |
| F-12 | Start the userspace stack twice against the same interface at once | Two independent programs attach and write to separate map instances, causing the dashboard to read an inconsistent view; identified as an operational hazard and documented as "run exactly one instance" rather than guarded in code, since guarding it was judged out of scope for a research prototype | Fail (documented limitation) |
| F-13 | Run the demo attack generator without root privileges | Raw-socket creation is denied by the OS as expected; the generator falls back to a weaker ICMP-based flood so a demonstration can still proceed without `sudo` | Pass |
| F-14 | Run the flash-crowd generator against the attached interface | Many short-lived connections are opened from distinct simulated ports; the corresponding source counters in `ip_count` increase without triggering the drop threshold at a normal setting | Pass |
| N-03 | Set an unusually low threshold while the dashboard itself is polling the API | The dashboard's own request traffic can itself cross a very low threshold and be dropped, silencing the dashboard; resolved for evaluation purposes by reading the BPF maps with `bpftool` instead, bypassing the API | Fail (documented limitation, evaluation methodology adjusted) |
| N-04 | Confirm dual persistence to SQLite and MongoDB Atlas | Every event and snapshot recorded by the collector is written to both the local SQLite database and the MongoDB Atlas mirror, so the system remains usable if the network connection to Atlas is unavailable | Pass |

Cases F-12 and N-03 are included deliberately despite not being straightforward passes.
Both were real issues found while developing and testing the system, and both shaped
the design of the evaluation methodology described in Section 6.3 - in
particular, the decision to measure results by reading the kernel maps straight rather
than through the dashboard's own API.

## Appendix C: Additional Use Case Specifications

The three specifications below expand on the use cases summarised in Section 4.4.1.

**Use Case: View Live Status**

| Field | Description |
|---|---|
| Actor | Operator |
| Precondition | The backend service is running; the dashboard is loaded in a browser |
| Main flow | The dashboard polls the status, top-sources, and events endpoints once per second; the API reads the current state from the BPF maps (if attached) or from the database, and returns it as JSON; the dashboard updates the counters, chart, and event list |
| Postcondition | The operator sees an up-to-date view of traffic, drops, and recent events with no more than a one-second delay |

**Use Case: Set Threshold Manually**

| Field | Description |
|---|---|
| Actor | Operator |
| Precondition | The XDP program is attached |
| Main flow | The operator enters a new threshold value and submits it; the API validates the value, writes it into the `config` BPF map, and disables adaptive mode so the manual value is not immediately overwritten; the change is logged as an event |
| Postcondition | The kernel program reads the new threshold on the very next packet; no reload occurs |

**Use Case: Start Attack Traffic (Demonstration)**

| Field | Description |
|---|---|
| Actor | Traffic Generator (invoked by the Operator for demonstration purposes) |
| Precondition | A target address is configured; the generator script is available on the host |
| Main flow | The operator specifies a target and rate; the API launches the attack-generation process; generated traffic reaches the XDP hook and is counted and, once over threshold, dropped, exactly as any other traffic would be |
| Postcondition | The dashboard reflects the resulting rise in seen and dropped packets, and the attacking source appears in the top-sources list marked as dropped |
</content>
