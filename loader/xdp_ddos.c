// Cerberus — M2: xdp_ddos.c  (TIER 1)
// Counts packets PER SOURCE IP. Drops any IP over the threshold.

#include <linux/bpf.h>
#include <linux/if_ether.h>   // struct ethhdr
#include <linux/ip.h>         // struct iphdr
#include <linux/in.h>

// MAP 1: IP -> packet count  (a table, many entries)
BPF_HASH(ip_count, u32, u64);

// MAP 2: the threshold. Kept in a map so userspace can change it live.
BPF_ARRAY(threshold, u64, 1);


int xdp_ddos(struct xdp_md *ctx) {

    // Where the packet starts and ends in memory
    void *data     = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;

    // --- Ethernet header ---
    struct ethhdr *eth = data;

    // BOUNDS CHECK: prove the packet is big enough before reading it
    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;

    // Only handle IPv4; everything else passes
    if (eth->h_proto != htons(ETH_P_IP))
        return XDP_PASS;

    // --- IP header (sits right after Ethernet) ---
    struct iphdr *ip = (void *)(eth + 1);

    // BOUNDS CHECK again
    if ((void *)(ip + 1) > data_end)
        return XDP_PASS;

    u32 src_ip = ip->saddr;        // who sent this packet

    // --- read the threshold ---
    int zero = 0;
    u64 *limit = threshold.lookup(&zero);

    if (!limit)
        return XDP_PASS;           // not set yet — do nothing

    if (*limit == 0)
        return XDP_PASS;           // 0 means "disabled" — safety

    // --- count this packet for this IP ---
    u64 init_value = 0;
    u64 *count = ip_count.lookup_or_try_init(&src_ip, &init_value);

    if (!count)
        return XDP_PASS;           // map full — fail open, don't block

    __sync_fetch_and_add(count, 1);

    // --- the decision ---
    if (*count > *limit) {
        return XDP_DROP;           // over the limit: kill the packet
    }

    return XDP_PASS;               // under the limit: let it through
}
