/*
 * xdp_ddos.c — Milestone M2+: Tier 1 DDoS filter at the XDP hook.
 *
 * WHAT THIS IS
 * ------------
 * The real kernel heart of Cerberus. For every IPv4 packet:
 *   1. Parse the Ethernet + IPv4 headers to get the source IP.
 *   2. Increment that IP's counter in the `ip_count` hash map.
 *   3. Compare against the live threshold in `config` map (key 0).
 *   4. XDP_DROP if over threshold; otherwise XDP_PASS.
 *
 * Userspace (loader, collector, control loop) reads/writes these maps.
 * Changing the threshold in `config` takes effect on the *next packet*
 * with no XDP reload — that is novelty 1's enabling mechanism (M4).
 *
 * MAP CONTRACT (shared with loader/collector/control_loop — keep in sync)
 * ----------------------------------------------------------------------
 *   ip_count   : BPF_HASH  key=u32 (IPv4 src, network byte order), value=u64
 *   config     : BPF_ARRAY key=u32 index 0 → threshold (u64 packets)
 *   totals     : BPF_ARRAY key=u32
 *                  0 = packets_seen
 *                  1 = packets_dropped
 *                  2 = packets_passed
 *
 * Soft/hard bands for ML escalation (M5) are applied in *userspace*; the
 * kernel stays deliberately simple: one threshold, drop or pass.
 *
 * HOW IT IS RUN
 * -------------
 *   sudo python3 loader/ddos_loader.py <interface> [--threshold N]
 */

#include <linux/if_ether.h>
#include <linux/ip.h>

/* Per-source-IP packet counters. Max entries keeps map memory bounded. */
BPF_HASH(ip_count, u32, u64, 10240);

/*
 * config[0] = drop threshold (packets counted for that src IP).
 * Userspace writes a new value here for live adaptive updates (M4).
 */
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
    if (eth->h_proto != htons(ETH_P_IP))
        return XDP_PASS;

    struct iphdr *iph = (void *)(eth + 1);
    if ((void *)(iph + 1) > data_end)
        return XDP_PASS;

    bump_total(0); /* packets_seen */

    u32 src = iph->saddr; /* already network byte order — use as map key */
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
