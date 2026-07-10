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
│   └── FOLDER_LAYOUT.md       # This file
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
│   ├── collector.py           # M3: reads BPF maps on a timer, writes to SQLite
│   ├── control_loop.py        # M4: adaptive threshold — writes new values to map
│   └── db.py                  # M3: SQLite schema + helpers (path via __file__)
│
├── cli/                       # M3 — the operator's steering wheel
│   └── ddosctl.py             # status / top / watch / threshold / clear commands
│
├── ml/                        # Tier 2 — the decision tree (M5)
│   ├── train_tree.py          # trains sklearn decision tree on CIC-IDS-2017
│   ├── classify.py            # loads trained tree, scores the ambiguous slice
│   └── model/                 # saved trained model (joblib) lives here
│
├── dashboard/                 # M3 — visualization
│   ├── index.html             # plain HTML + Chart.js dashboard
│   └── data/                  # JSON the dashboard reads (written by collector)
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
├── requirements.txt           # Python deps for the ML/analysis venv
└── .gitignore                 # ignore data/, model binaries, __pycache__, *.db
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
| M3 | `backend/collector.py`, `backend/db.py`, `cli/ddosctl.py`, `dashboard/` |
| M4 | `backend/control_loop.py` |
| M5 | `ml/` (train, classify, model), `requirements.txt`, `data/cic-ids-2017/` |
| M6 | `attack/`, `eval/` |
