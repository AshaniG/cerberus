/*
 * hello_xdp.c — Milestone M0: the smallest possible eBPF/XDP program.
 *
 * WHAT THIS IS
 * ------------
 * This is Tier 1's "hello world". It attaches at the XDP hook — the earliest
 * software checkpoint a packet reaches, right as it leaves the network card's
 * driver and *before* the normal Linux networking stack — and simply lets
 * every packet continue on its way (XDP_PASS).
 *
 * WHY IT EXISTS
 * -------------
 * It proves the whole toolchain works on this machine: BCC can compile
 * restricted C, the kernel's eBPF verifier accepts the program, and the NIC
 * accepts an XDP attachment. Setup friction (kernel headers, driver support,
 * permissions) is the project's biggest time risk, so we hit it on day one
 * with the simplest program possible. No maps, no parsing, no dropping —
 * those arrive in M1 and M2.
 *
 * HOW IT IS RUN
 * -------------
 * This file is never compiled by hand. The BCC loader (loader/hello_loader.py)
 * reads this source, compiles it on the spot for the running kernel, and
 * attaches it to a network interface. Run:  sudo python3 loader/hello_loader.py <iface>
 */

/*
 * The function below is the entire eBPF program. The kernel calls it once for
 * EVERY packet that arrives on the interface it is attached to — this is the
 * "hot path", so anything here must be tiny and fast.
 *
 * The argument `ctx` describes the raw packet (where its bytes start and end
 * in memory). We don't look at the packet at all in M0, but the verifier still
 * requires the standard XDP signature, so the argument must be here.
 */
int hello_xdp(struct xdp_md *ctx)
{
    /*
     * bpf_trace_printk writes a line into the kernel's shared trace buffer
     * (/sys/kernel/debug/tracing/trace_pipe). It is a debugging tool only —
     * far too slow for real use, since it fires for every single packet —
     * but for M0 it is perfect: if lines appear, we have hard proof that our
     * code is genuinely running inside the kernel for each packet.
     * The loader reads these lines and shows them to us.
     */
    bpf_trace_printk("hello_xdp: packet seen\n");

    /*
     * XDP_PASS tells the kernel: "carry on as normal" — hand the packet up
     * to the regular networking stack as if we were never here. The other
     * verdict we will care about later is XDP_DROP (M2), which discards the
     * packet immediately. M0 must never interfere with traffic, so we pass
     * everything.
     */
    return XDP_PASS;
}
