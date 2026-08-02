# Cerberus

**Kernel-level, two-tier, online-adaptive DDoS detection using eBPF/XDP.**

A cheap statistical filter runs in the Linux kernel at the XDP hook (Tier 1);
only ambiguous traffic escalates to a small ML decision tree in userspace
(Tier 2); a userspace control loop updates detection thresholds live via BPF maps
**without reloading** the kernel program. The research shows this design keeps
false positives low against legitimate flash-crowd surges while still detecting
real attacks — beating a static-threshold baseline.
    
## Start here

0. **Feeling lost about how the parts connect?** Read [`docs/HOW_IT_ALL_CONNECTS.md`](docs/HOW_IT_ALL_CONNECTS.md) — attack → kernel → maps → backend → ML → dashboard, in plain language.
1. Read [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md) — architecture, novelty, milestones.
2. Follow [`docs/SETUP_GUIDE.md`](docs/SETUP_GUIDE.md) — Ubuntu 24.04 + BCC.
3. **Run the system:** [`docs/HOW_TO_RUN.md`](docs/HOW_TO_RUN.md) — step-by-step Ubuntu commands.
4. **Done vs remaining (+ optional more):** [`docs/STATUS.md`](docs/STATUS.md) — show this for viva readiness.
5. Optional Atlas: [`docs/MONGODB_ATLAS.md`](docs/MONGODB_ATLAS.md).
6. Supervisor demo: [`docs/SUPERVISOR_DEMO.md`](docs/SUPERVISOR_DEMO.md).

## Quick run (Ubuntu, as root)

```bash
# Toolchain check
python3 -c "from bcc import BPF; print('BCC OK')"

# Install API/ML deps into the same Python sudo will use
sudo pip3 install -r requirements.txt

# Full stack: XDP + collector + adaptive control + dashboard
sudo python3 backend/serve.py eth0 --threshold 250 --port 8080
# → open http://<host-ip>:8080/
```

Milestone loaders (standalone):

```bash
sudo python3 loader/hello_loader.py eth0      # M0
sudo python3 loader/count_loader.py eth0      # M1
sudo python3 loader/ddos_loader.py eth0       # M2
```

CLI (against running API):

```bash
python3 cli/ddosctl.py status
python3 cli/ddosctl.py top
python3 cli/ddosctl.py watch
```

Train Tier-2 tree (optional but recommended before demo):

```bash
python3 ml/train_tree.py          # uses CIC-IDS if present, else synthetic
```

Evaluation:

```bash
python3 eval/run_experiment.py --target <host-ip>
```

## Stack

| Layer | Choice |
|-------|--------|
| Tier 1 | eBPF/XDP (BCC) |
| Tier 2 | scikit-learn decision tree |
| Adaptive control | userspace → BPF `config` map |
| Storage | SQLite (truth) + optional MongoDB Atlas mirror |
| API / UI | FastAPI + HTML/Chart.js |
| Attack / FP test | hping3 + flash-crowd generator |

## Build order

M0 → M1 → M2 → M3 (API/dashboard) → M4 (adaptive) → M5 (ML) → M6 (eval).
Protect the three novelties; avoid scope creep. Details in `docs/PROJECT_CONTEXT.md`.
