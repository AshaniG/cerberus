 # How Cerberus all connects (read this when you feel lost)

This is the "big picture" document. It does **not** add new code — every part below
already exists in the repo. Its only job is to show you, in plain language, **how the
pieces talk to each other**: attack traffic → Ubuntu kernel → BPF maps → backend →
machine learning → dashboard. Read it once, slowly, and the whole system will click.

If you remember only one sentence:

> **The attack sends packets → the kernel counts and drops them → BPF maps are the
> shared notice-board between kernel and Python → the Python backend reads that
> notice-board and shows it on the dashboard, escalating suspicious IPs to the ML tree,
> and writes a new threshold back onto the notice-board so the kernel adapts live.**

---

## 1. The one picture

```
            ┌──────────────────────────────────────────────────────────────┐
            │                     ONE UBUNTU MACHINE                        │
            │                                                              │
 attacker   │   ┌── KERNEL (fast, per-packet) ──────────────┐              │
 traffic    │   │                                           │              │
 ────────▶  NIC │  XDP hook → xdp_ddos.c                     │              │
 (hping3,   │   │     • count this source IP                 │              │
 flashcrowd)│   │     • DROP if count ≥ threshold, else PASS │              │
            │   │                    ▲        │              │              │
            │   └────────────────────┼────────┼──────────────┘              │
            │                        │        │                            │
            │              writes    │        │  reads                     │
            │            threshold   │        ▼  counts                    │
            │              ┌─────────┴─────── BPF MAPS ───────────┐         │
            │              │  ip_count  (per-IP counters)         │         │
            │              │  config[0] (the live threshold)      │         │
            │              │  totals    (seen / dropped / passed) │         │
            │              └───────▲───────────────┬──────────────┘         │
            │                      │               │                        │
            │   ┌── USERSPACE (Python, a few times/sec) ─────────────┐      │
            │   │  control_loop.py ─┘ (writes new threshold)         │      │
            │   │  collector.py ◀────┘ (reads counts on a timer)     │      │
            │   │      │        └─▶ ambiguous IP? ─▶ ml/classify.py  │      │
            │   │      ▼                              (decision tree)│      │
            │   │  db.py → SQLite (data/cerberus.db)                 │      │
            │   │      ▲                                             │      │
            │   │  api.py (FastAPI) ── serves ──▶ dashboard/*        │      │
            │   └──────────────────────────────────────────────────┘      │
            └──────────────────────────────┬───────────────────────────────┘
                                           │  http://<host>:8080
                                           ▼
                                    Your web browser
                              (index.html + app.js + Chart.js)
```

**The single most important idea:** the kernel and Python are two separate worlds.
They *cannot* call each other directly. The **BPF maps** are the only bridge — a small
shared memory the kernel writes and Python reads (counts going **up**), and Python
writes and the kernel reads (threshold going **down**). Everything else hangs off that.

---

## 2. Who is who (each part in one line)

| Part | File(s) | What it is | Runs where |
|---|---|---|---|
| **Attack generator** | [`attack/attack_gen.py`](../attack/attack_gen.py) | Fires a SYN flood at the machine (via `hping3`) | userspace |
| **Flash-crowd generator** | [`attack/flashcrowd_gen.py`](../attack/flashcrowd_gen.py) | Fires *legitimate-looking* surge traffic | userspace |
| **Tier 1 (the kernel filter)** | [`kernel/xdp_ddos.c`](../kernel/xdp_ddos.c) | Counts each IP, drops over threshold | **kernel** |
| **BPF maps** | *(declared inside `xdp_ddos.c`)* | The shared notice-board | kernel memory |
| **Session handle** | [`backend/bpf_session.py`](../backend/bpf_session.py) | Python's grip on the maps (read/write) | userspace |
| **Collector** | [`backend/collector.py`](../backend/collector.py) | Reads maps every 1s, saves to DB, escalates | userspace |
| **Control loop (adaptive)** | [`backend/control_loop.py`](../backend/control_loop.py) | Computes + writes a new threshold live | userspace |
| **Tier 2 (the ML)** | [`ml/classify.py`](../ml/classify.py), [`ml/train_tree.py`](../ml/train_tree.py) | Decision tree that judges ambiguous IPs | userspace |
| **Database** | [`backend/db.py`](../backend/db.py) → `data/cerberus.db` | Stores history (source of truth) | userspace |
| **API** | [`backend/api.py`](../backend/api.py) | Web endpoints the dashboard calls | userspace |
| **Dashboard** | [`dashboard/index.html`](../dashboard/index.html), [`app.js`](../dashboard/app.js) | The screen you look at | your browser |
| **The conductor** | [`backend/serve.py`](../backend/serve.py) | Starts ALL of the above in one process | userspace |

---

## 3. Follow ONE attack packet through the whole system

This is the part that makes it click. Imagine you run an attack. Follow a single packet:

1. **You start the attack.** `hping3` (driven by [`attack/attack_gen.py`](../attack/attack_gen.py))
   sends thousands of packets at the Ubuntu machine's IP.

2. **The packet hits the network card (NIC),** then immediately reaches the **XDP hook** —
   the earliest point in Linux, *before* the normal network stack. Your program
   [`kernel/xdp_ddos.c`](../kernel/xdp_ddos.c) runs here, once for this packet.

3. **The kernel program does 4 tiny things** ([`xdp_ddos.c:58-98`](../kernel/xdp_ddos.c#L58-L98)):
   - reads the packet's **source IP**,
   - adds 1 to that IP's counter in the **`ip_count`** map,
   - reads the current **threshold** from the **`config`** map,
   - if `count ≥ threshold` → **`XDP_DROP`** (packet dies here, never wastes CPU) and
     bumps the `dropped` tally; otherwise **`XDP_PASS`** and bumps `passed`.

   👉 This is the whole "attack → Ubuntu kernel" story. The attack never gets deep into
   the machine — it's stopped at the doormat.

4. **The counts now live in the BPF maps** (kernel memory). The kernel's job is done.
   It did **not** call Python. It just left numbers on the notice-board.

5. **One second later, the collector wakes up.** [`backend/collector.py`](../backend/collector.py)
   asks [`backend/bpf_session.py`](../backend/bpf_session.py) to **read** the maps:
   totals + the top talking IPs. `bpf_session` is literally Python holding the same map
   objects the kernel writes ([`bpf_session.py:94-120`](../backend/bpf_session.py#L94-L120)).

6. **The collector saves a snapshot** to SQLite via [`backend/db.py`](../backend/db.py)
   ([`collector.py:62-68`](../backend/collector.py#L62-L68)) — this becomes the chart and
   history on the dashboard.

7. **The ML branch (Tier 2).** For each top IP the collector checks: is this IP in the
   *ambiguous band* (between `soft = 60% of threshold` and the hard threshold)?
   ([`collector.py:93-105`](../backend/collector.py#L93-L105))
   - If yes → it records an **`escalate`** event and calls
     [`ml/classify.py`](../ml/classify.py) → `classify_flow(...)`.
   - The decision tree (trained by [`ml/train_tree.py`](../ml/train_tree.py), saved as
     `ml/model/tree.joblib`) returns **`attack`** or **`benign`** with a score.
   - That verdict is saved as an **`ml`** event.
   - **This is novelty 2:** the cheap kernel filter handles *everything*; only the small
     ambiguous slice ever reaches the ML. Clean traffic and obvious attacks never touch it.

8. **The dashboard shows it.** Your browser runs [`dashboard/app.js`](../dashboard/app.js),
   which every 1 second calls four API endpoints on [`backend/api.py`](../backend/api.py):
   `/api/status`, `/api/top`, `/api/events`, `/api/timeseries`
   ([`app.js:103-108`](../dashboard/app.js#L103-L108)). The API reads the live maps + the
   SQLite history and returns JSON; `app.js` paints the numbers, the chart, the top-IP
   table, and the events list.

9. **The system adapts (novelty 1).** Separately, every ~2 seconds
   [`backend/control_loop.py`](../backend/control_loop.py) looks at the recent traffic rate
   and computes a smarter threshold. It **writes that new number into the `config` map**
   ([`control_loop.py:110`](../backend/control_loop.py#L110)). The *very next packet* in the
   kernel reads the new threshold — **no reload, no restart.** That live write-down is the
   defining trick of the whole project.

That's the entire loop. Counts flow **up** (kernel → maps → Python → dashboard).
The threshold flows **down** (Python → map → kernel). The ML sits on the side, consulted
only for the doubtful cases.

---

## 4. The three connections you were unsure about — spelled out

**"How does the DDoS attack reach the Ubuntu kernel?"**
The attack tool sends normal network packets to the machine's IP. Every packet entering
the NIC passes the XDP hook *first*, so your kernel program sees and judges it before the
rest of Linux does. You don't "connect" the attacker to the kernel — the kernel simply
sits at the gate every packet must cross.

**"How does the dashboard connect to the backend and the maps?"**
The dashboard is just a web page. It never touches the kernel. It makes HTTP calls to the
FastAPI backend ([`api.py`](../backend/api.py)). The backend, being in the **same process**
as the XDP session, holds the map objects through [`bpf_session.py`](../backend/bpf_session.py)
and reads them for you. So: **browser → HTTP → api.py → bpf_session → BPF maps.**
Buttons work the same way in reverse: click "Set threshold" → `POST /api/threshold` →
`api.py` → `bpf_session.set_threshold()` → writes the `config` map.

**"How does the backend connect to the ML part?"**
The collector imports the classifier and calls it only for ambiguous IPs:
`from ml.classify import classify_flow` ([`collector.py:111-119`](../backend/collector.py#L111-L119)).
`classify.py` loads the trained tree file `ml/model/tree.joblib`. If you haven't trained
yet, that file is missing and the call safely does nothing (no crash) — which is why
training (`python3 ml/train_tree.py`) is the one step that "switches the ML on."

**Why one process?** [`backend/serve.py`](../backend/serve.py) starts the XDP session, the
collector, the control loop, and the API **together**. They share the same BPF maps because
they're the same program. That's the reason the whole stack is `sudo python3 backend/serve.py`
and not five separate services.

---

## 5. See the flow live (do this on Ubuntu)

```bash
# 1. Start everything (kernel filter + collector + adaptive + ML + dashboard)
sudo python3 backend/serve.py eth0 --port 8080     # use your real interface from `ip link show`

# 2. Open the dashboard in a browser
#    http://<this-machine-ip>:8080/
#    Top badges should read: Tier-1 ON · LIVE  (not "UI PREVIEW")

# 3. From ANOTHER terminal, train the ML once so the tree file exists
python3 ml/train_tree.py       # creates ml/model/tree.joblib → badge flips to "ML ready"

# 4. Fire an attack at the machine and WATCH the dashboard
sudo python3 attack/attack_gen.py --target <this-machine-ip> --rate 300 --duration 20
#    → "Seen" climbs, the attacking IP appears in Top sources and turns to "drop",
#      "Dropped" climbs, and drop/escalate/ml events stream in Recent events.

# 5. Turn Adaptive ON, then run the flash crowd (legitimate surge)
#    → fewer false drops than a low static threshold. THIS is your research result.
sudo python3 attack/flashcrowd_gen.py --target <this-machine-ip> --rate 120 --duration 20
```

Watching that screen while step 4 runs is the moment every connection in this document
becomes real: attack → kernel counts → map → collector → DB + ML → API → your eyes.

---

## 6. "Do I need to add more parts?" — No

Every block in the diagram is already written and, where possible off-Ubuntu, already
tested. What remains is **not writing new code** — it is:

1. Run it on the Ubuntu machine (needs root + a real kernel — steps above).
2. Train the ML once (`python3 ml/train_tree.py`; optionally on real CIC-IDS-2017 later).
3. Record the attack-vs-flash-crowd numbers with `python3 eval/run_experiment.py --target <ip>`.

If you ever want to *strengthen* the project (optional, only after the above is green),
the highest-value additions are all in [`docs/STATUS.md §3`](STATUS.md) — e.g. training on
the real dataset and running the evaluation several times. None of them change the
architecture in this document.

---

## 7. Where to look when something specific confuses you

| Your question | Open this |
|---|---|
| What is the research actually about? | [`docs/PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) |
| How do I install / run it on Ubuntu? | [`docs/HOW_TO_RUN.md`](HOW_TO_RUN.md) |
| What's done vs still to do? | [`docs/STATUS.md`](STATUS.md) |
| How the kernel filter works, line by line | [`kernel/xdp_ddos.c`](../kernel/xdp_ddos.c) (comments) |
| How maps are read/written from Python | [`backend/bpf_session.py`](../backend/bpf_session.py) |
| How the dashboard talks to the backend | [`dashboard/app.js`](../dashboard/app.js) |
| Demo script for the supervisor | [`docs/SUPERVISOR_DEMO.md`](SUPERVISOR_DEMO.md) |
</content>
</invoke>
