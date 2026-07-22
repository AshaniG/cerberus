// Cerberus — M1: count_all.c
// Counts every packet into ONE number in a BPF map. Blocks nothing.

#include <linux/bpf.h>

// A map with 1 slot holding a 64-bit counter.
// Both kernel and Python can see this.
BPF_ARRAY(packet_count, u64, 1);

int count_all(struct xdp_md *ctx) {

    int key = 0;                              // our array has only slot 0

    u64 *count = packet_count.lookup(&key);   // get pointer to the counter

    if (count) {                              // null check — verifier REQUIRES this
        __sync_fetch_and_add(count, 1);       // add 1 safely across CPU cores
    }

    return XDP_PASS;                          // always let the packet through
}
