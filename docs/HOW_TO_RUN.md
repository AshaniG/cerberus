# Cerberus — how to run (Ubuntu)

Follow this top to bottom on **bare-metal Ubuntu 24.04**.  
Mac/Windows can edit code and smoke-test the dashboard UI only — **eBPF/XDP must run on Ubuntu**.

---

## 0. One-time machine setup

```bash
sudo apt update && sudo apt upgrade -y

sudo apt install -y \
  bpfcc-tools libbpfcc libbpfcc-dev python3-bpfcc \
  linux-headers-$(uname -r) \
  clang llvm libelf-dev build-essential \
  linux-tools-common linux-tools-$(uname -r) \
  hping3 python3-pip python3-venv git sqlite3
```

Verify:

```bash
lsb_release -a
uname -r
python3 -c "from bcc import BPF; print('BCC OK')"
sudo bpftool version
ip link show          # note your iface, e.g. eth0 / enp3s0
hping3 --version
```

Prefer a **wired** interface. Wi‑Fi often needs SKB/generic XDP (the loaders fall back automatically).

Clone / pull the repo, then:

```bash
cd ~/cerberus   # or your path
sudo pip3 install -r requirements.txt
```

Optional ML model (recommended before supervisor demo):

```bash
python3 ml/train_tree.py
# For real thesis numbers later: put CIC-IDS-2017 CSVs in data/cic-ids-2017/
# then: python3 ml/train_tree.py
```

Optional MongoDB Atlas mirror: see [`docs/MONGODB_ATLAS.md`](docs/MONGODB_ATLAS.md)  
(`cp .env.example .env` and fill `MONGODB_URI`).

---

## 1. Milestone smoke tests (optional but smart)

Do these once so you know the toolchain is solid.

```bash
# M0 — hello XDP
sudo python3 loader/hello_loader.py eth0
# ping this host from another machine; you should see "packet seen". Ctrl+C.

# M1 — global counter
sudo python3 loader/count_loader.py eth0
# counter should climb. Ctrl+C.

# M2 — per-IP + drop
sudo python3 loader/ddos_loader.py eth0 --threshold 100
# flood with hping3 from another host; that IP should appear and get dropped. Ctrl+C.
```

Replace `eth0` with your real interface name.

---

## 2. Full product (what you show the supervisor)

**Terminal A — start everything (XDP + collector + adaptive + API + dashboard):**

```bash
cd ~/cerberus
sudo python3 backend/serve.py eth0 --threshold 250 --port 8080
```

Open in a browser (on Ubuntu or another laptop on the same LAN):

```text
http://<ubuntu-ip>:8080/
```

You should see badges: **Tier-1 ON**, **LIVE** (not “UI PREVIEW”).

**Terminal B — CLI (optional):**

```bash
python3 cli/ddosctl.py status
python3 cli/ddosctl.py top
python3 cli/ddosctl.py watch
python3 cli/ddosctl.py events
```

---

## 3. Demo traffic (from the UI or CLI)

On the dashboard:

1. Set **Target IP** = this Ubuntu machine’s IP (`ip -4 addr`).
2. Click **Start attack** → Seen / top IP / Dropped should move (live XDP).
3. Click **Adaptive ON**, then **Start flash crowd** → threshold can move; fewer false drops than a harsh static threshold.
4. Click **Adaptive OFF**, set a low threshold (e.g. 50), flash crowd again → more false drops (the contrast for novelty 3).

Or from a second machine / terminal:

```bash
# Attack (often needs sudo for hping3)
sudo python3 attack/attack_gen.py --target <ubuntu-ip> --rate 250 --duration 30

# Flash crowd (legit-like surge)
python3 attack/flashcrowd_gen.py --target <ubuntu-ip> --rate 120 --duration 40
```

Supervisor script (minute-by-minute talking points): [`docs/SUPERVISOR_DEMO.md`](docs/SUPERVISOR_DEMO.md).

---

## 4. Evaluation numbers (thesis / M6)

With `serve.py` already running:

```bash
python3 eval/run_experiment.py --target <ubuntu-ip> --api http://127.0.0.1:8080
```

Results land in:

- `eval/results/experiment_*.csv` / `.json`
- `eval/figures/experiment_*.png` (if matplotlib works)

---

## 5. Common problems

| Symptom | Fix |
|--------|-----|
| `from bcc import BPF` fails | Reinstall `python3-bpfcc` + matching `linux-headers-$(uname -r)` |
| Native XDP attach fails | Loader/serve falls back to SKB mode — OK for this project |
| Dashboard empty / connection refused | Is `serve.py` still running? Correct IP/port? |
| Seen stays 0 with serve.py | Wrong iface; or traffic not hitting that NIC |
| Attack button does nothing useful | Install `hping3`; Target IP must be the Ubuntu host |
| Atlas OFF | Optional — detection does not need it |
| Kernel controls disabled on Mac | Expected — use Ubuntu `serve.py` for live controls |

Stop cleanly: **Ctrl+C** in the `serve.py` terminal (it detaches XDP).

---

## 6. What “done” means

**Code in this repo is complete** for M0–M6 (kernel, API, dashboard, adaptive, ML hooks, attack/eval, docs).

**You still do on Ubuntu:**

1. Run §0–§2 and confirm **Tier-1 ON / LIVE**.  
2. Run the supervisor demo (§3 + `docs/SUPERVISOR_DEMO.md`).  
3. Run `eval/run_experiment.py` and keep the CSV/figure for the thesis.  
4. (Optional) Atlas + real CIC-IDS training for stronger ML claims.

That is the path to a high-marks, runnable viva demo.
