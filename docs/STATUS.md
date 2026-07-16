# Cerberus — project status (done vs remaining)

**Share this file** when someone asks what is finished and what still needs to be done.  
Full run steps: [`HOW_TO_RUN.md`](HOW_TO_RUN.md) · Supervisor talk track: [`SUPERVISOR_DEMO.md`](SUPERVISOR_DEMO.md)

**Last updated:** July 2026  
**Repo state:** implementation complete for M0–M6; **Ubuntu live verification + training/eval runs** are the remaining work for viva.

---

## 1. What is DONE (in the codebase)

| Area | Status | Where |
|------|--------|--------|
| M0 Hello XDP | Done | `kernel/hello_xdp.c`, `loader/hello_loader.py` |
| M1 Global counter | Done | `kernel/count_all.c`, `loader/count_loader.py` |
| M2 Tier-1 per-IP + DROP | Done | `kernel/xdp_ddos.c`, `loader/ddos_loader.py` |
| M3 Backend + SQLite | Done | `backend/db.py`, `collector.py`, `bpf_session.py` |
| M3 FastAPI + dashboard FE | Done | `backend/api.py`, `backend/serve.py`, `dashboard/` |
| M3 CLI | Done | `cli/ddosctl.py` |
| MongoDB Atlas (optional mirror) | Done (code) | `backend/mongo.py`, `docs/MONGODB_ATLAS.md`, `.env.example` |
| M4 Adaptive threshold | Done | `backend/control_loop.py` (live BPF map write, no reload) |
| M5 ML train + classify | Done (code) | `ml/train_tree.py`, `ml/classify.py` |
| M6 Attack generator | Done | `attack/attack_gen.py` |
| M6 Flash-crowd generator | Done | `attack/flashcrowd_gen.py` |
| M6 Eval harness | Done | `eval/run_experiment.py` |
| Docs / runbook | Done | `HOW_TO_RUN.md`, `SETUP_GUIDE.md`, `SUPERVISOR_DEMO.md`, this file |
| Mac UI smoke test | Done | Dashboard + attack/flash + UI preview mode verified |

**Not done as “production SaaS”** (and not required for FYP): multi-node, React SPA, auth/SSO, hard dependency on Atlas.

---

## 2. What REMAINS (you / on Ubuntu machine)

Do these in order. Until §A–C are green, the viva demo is not fully proven.

### A. Environment (once)

- [ ] Ubuntu **24.04** bare metal + BCC OK (`python3 -c "from bcc import BPF; print('BCC OK')"`)
- [ ] `sudo pip3 install -r requirements.txt`
- [ ] Note interface name: `ip link show`
- [ ] Optional: Atlas `.env` (see `MONGODB_ATLAS.md`) — nice for demo, **not** required for marks

### B. Live product check (required for viva)

- [ ] `sudo python3 backend/serve.py <iface> --port 8080`
- [ ] Browser: **Tier-1 ON** and **LIVE** (not “UI PREVIEW”)
- [ ] Normal traffic → **Seen** rises
- [ ] Start attack (Target = Ubuntu IP) → top IP + **Dropped** rise
- [ ] Adaptive ON + flash crowd → fewer false drops than low static threshold
- [ ] `python3 cli/ddosctl.py status` / `top` / `events` works

### C. ML (code done — you must train the model)

- [ ] Quick: `python3 ml/train_tree.py` → creates `ml/model/tree.joblib`
- [ ] Stronger (thesis): download CIC-IDS-2017 into `data/cic-ids-2017/`, then train again
- [ ] Confirm dashboard **ML ready** and/or an `ml` / `escalate` event after ambiguous traffic

### D. Evaluation numbers (thesis / viva evidence)

- [ ] With serve.py running: `python3 eval/run_experiment.py --target <ubuntu-ip>`
- [ ] Keep `eval/results/*.csv` and `eval/figures/*.png` for results chapter
- [ ] Practice [`SUPERVISOR_DEMO.md`](SUPERVISOR_DEMO.md) once end-to-end (~12 min)

---

## 3. One-line summary you can say

> **“Implementation of the full Cerberus stack (eBPF Tier‑1, adaptive control, selective ML, API/dashboard, attack/eval) is complete in the repo. Remaining work is running it on Ubuntu, training the ML model, and capturing eval results for the viva.”**

---

## 4. Quick pointer map

| Question | Open this |
|----------|-----------|
| How do I run it? | [`HOW_TO_RUN.md`](HOW_TO_RUN.md) |
| What is the research about? | [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) |
| Machine install | [`SETUP_GUIDE.md`](SETUP_GUIDE.md) |
| Supervisor demo script | [`SUPERVISOR_DEMO.md`](SUPERVISOR_DEMO.md) |
| Mongo Atlas (optional) | [`MONGODB_ATLAS.md`](MONGODB_ATLAS.md) |
| Done vs remaining | **This file** (`STATUS.md`) |
