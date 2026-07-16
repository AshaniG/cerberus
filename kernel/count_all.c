/*
 * count_all.c — Milestone M1: global packet counter in a BPF map.
 *
 * WHAT THIS IS
 * ------------
 * The next step after hello_xdp (M0). Still attached at the XDP hook, still
 * passes every packet (XDP_PASS) — but now it also increments a single
 * counter stored in a BPF map. Userspace (loader/count_loader.py) reads that
 * map once per second and prints the total. This proves the *only* bridge
 * between kernel and userspace works: BPF maps.
 *
 * WHY IT EXISTS
 * -------------
 * M0 proved we can attach. M1 proves we can share state. Every later
 * milestone (per-IP counts, live threshold updates, the collector) rests on
 * this same map read/write pattern.
 *
 * HOW IT IS RUN
 * -------------
 * Never compiled by hand. BCC compiles it at load time:
 *   sudo python3 loader/count_loader.py <interface>
 */

/* Single-slot array: key 0 holds the running packet total. */
BPF_ARRAY(pkt_count, u64, 1);

int count_all(struct xdp_md *ctx)
{
    u32 key = 0;
    u64 *value;
    u64 zero = 0;

    /*
     * lookup_or_init returns a pointer to the map slot. On the first packet
     * the slot does not exist yet, so BCC inserts `zero` for us. After that
     * we just bump the value. The verifier requires a null check.
     */
    value = pkt_count.lookup_or_init(&key, &zero);
    if (value) {
        __sync_fetch_and_add(value, 1);
    }

    /* Never interfere with traffic in M1 — counting only. */
    return XDP_PASS;
}
