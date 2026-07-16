# Cerberus — folder layout

> The intended structure for the whole project. Each part of the system has one
> obvious home, and the layout maps onto the milestones in `PROJECT_CONTEXT.md`
> §5. You do NOT create all of this on day one — folders appear as their milestone
> arrives. This is the target shape.

```
cerberus/
│
├── README.md                  # Entry point; points to docs/
│
├── docs/                      # All project documentation
│   ├── PROJECT_CONTEXT.md     # What/why/how — the source of truth (read first)
│   ├── SETUP_GUIDE.md         # Environment setup steps
│   ├── FOLDER_LAYOUT.md       # This file
│   ├── MONGODB_ATLAS.md       # Atlas setup for optional mirror
│   ├── SUPERVISOR_DEMO.md     # 12-minute viva / supervisor script
│   ├── HOW_TO_RUN.md          # Step-by-step Ubuntu runbook (start here to demo)
│   └── STATUS.md              # Done vs remaining (share for viva readiness)
│
├── kernel/                    # Tier 1 — the in-kernel eBPF programs (restricted C)
│   ├── hello_xdp.c            # M0: attach at XDP hook, pass all packets
│   ├── count_all.c            # M1: single global packet counter in a BPF map
│   └── xdp_ddos.c             # M2+: per-source-IP counting, threshold, DROP
│
├── loader/                    # BCC Python loaders that compile + attach the eBPF
│   ├── hello_loader.py        # M0: loads hello_xdp.c, confirms it attaches
│   ├── count_loader.py        # M1: loads count_all.c, reads the counter map
│   └── ddos_loader.py         # M2+: loads xdp_ddos.c, exposes the maps
│
├── backend/                   # Cold-path userspace services (Python)
│   ├── serve.py               # M3+: one process — XDP + collector + control + API
│   ├── api.py                 # FastAPI REST + static dashboard
│   ├── bpf_session.py         # Shared attach / map read-write (map contract)
│   ├── collector.py           # Reads BPF maps → SQLite (+ Atlas mirror)
│   ├── control_loop.py        # M4: adaptive threshold → live map write
│   ├── db.py                  # SQLite schema + helpers (path via __file__)
│   ├── mongo.py               # Optional MongoDB Atlas client (no-op if unset)
│   └── runtime_state.py       # Shared flags for API (attack demo, adaptive, ml)
│
├── cli/                       # M3 — the operator's steering wheel
│   └── ddosctl.py             # status / top / watch / threshold / clear / events
│
├── ml/                        # Tier 2 — the decision tree (M5)
│   ├── train_tree.py          # trains sklearn decision tree on CIC-IDS-2017
│   ├── classify.py            # loads trained tree, scores the ambiguous slice
│   └── model/                 # saved trained model (joblib) lives here
│
├── dashboard/                 # M3 — ops console (served by FastAPI)
│   ├── index.html
│   ├── styles.css
│   └── app.js
│
├── attack/                    # M6 — traffic generation for evaluation
│   ├── attack_gen.py          # hping3 wrapper — synthetic DDoS traffic
│   └── flashcrowd_gen.py      # legitimate surge traffic (the FP test — key novelty)
│
├── eval/                      # M6 — experiments + results
│   ├── run_experiment.py      # orchestrates a run: config → traffic → measure
│   ├── results/               # raw measurement output (CSV/JSON) per run
│   └── figures/               # plots generated for the thesis
│
├── data/                      # datasets + the live SQLite file
│   ├── cic-ids-2017/          # downloaded CIC-IDS-2017 CSVs (gitignored)
│   └── cerberus.db            # SQLite database (gitignored)
│
├── .env.example               # MONGODB_URI template (copy to .env)
├── requirements.txt           # Python deps for API / ML / eval
└── .gitignore
```

## Notes on a few deliberate choices

- **`kernel/` and `loader/` are separate.** The `.c` files are the eBPF programs
  (hot path). The `loader/*.py` files are the BCC scripts that compile and attach
  them. Keeping them apart makes obvious which code runs in the kernel and which
  runs in userspace — an important conceptual line in this project.
- **`db.py` computes its path from `__file__`.** A past version had a bug where the
  collector and CLI created *separate* SQLite files depending on the working
  directory. Always resolve the DB path relative to the module's own location so
  every component opens the same database.
- **`attack/` and `eval/` are separate.** `attack/` just *produces traffic*.
  `eval/` *runs the experiment and records numbers*. The flash-crowd generator in
  `attack/` is small but carries the project's most important novelty — treat it
  seriously.
- **`data/` and model binaries are gitignored.** CIC-IDS-2017 is large and the
  SQLite file changes constantly; neither belongs in version control.

## Milestone → folder map

| Milestone | New files/folders |
|---|---|
| M0 | `kernel/hello_xdp.c`, `loader/hello_loader.py` |
| M1 | `kernel/count_all.c`, `loader/count_loader.py` |
| M2 | `kernel/xdp_ddos.c`, `loader/ddos_loader.py` |
| M3 | `backend/{serve,api,bpf_session,collector,db,mongo}.py`, `cli/ddosctl.py`, `dashboard/` |
| M4 | `backend/control_loop.py` |
| M5 | `ml/` (train, classify, model), `requirements.txt`, `data/cic-ids-2017/` |
| M6 | `attack/`, `eval/`, `docs/SUPERVISOR_DEMO.md` |
