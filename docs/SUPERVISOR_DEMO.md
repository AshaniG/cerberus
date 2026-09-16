# Cerberus — Supervisor demo script (10–12 minutes)

Use this checklist during a live viva / supervisor review. Run on **Ubuntu 24.04**
with XDP attached. Laptop browsers can open the dashboard over LAN.

## Before the meeting (once)

1. Install toolchain from `docs/SETUP_GUIDE.md` (BCC OK, hping3 present).
2. Optional Atlas: follow `docs/MONGODB_ATLAS.md` and place URI in `.env`.
3. Optional ML: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python3 ml/train_tree.py`
4. Note your iface (`ip link show`) and this host’s IP (`ip -4 addr`).

## Start the system

```bash
cd ~/cerberus   # or your clone path
sudo python3 backend/serve.py <iface> --threshold 100 --port 8080
```

Open `http://<host-ip>:8080/` on the projector / supervisor laptop.

## Live narrative (≈12 min)

| Min | What you show | What you say |
|-----|---------------|--------------|
| 0–1 | Dashboard idle | Cerberus sits at the **XDP** hook — earliest software gate. Tier 1 is in-kernel; Tier 2/ML and adaptive control are userspace. |
| 1–2 | Badges | Tier-1 ON, Adaptive, ML ready/pending, Atlas ON/OFF. SQLite is always local truth; Atlas is a live mirror. |
| 2–5 | **Start attack** (set Target = host IP, rate ~200) | SYN flood from hping3. Top sources climb; **Dropped** rises once count ≥ threshold. Kernel returns `XDP_DROP`. |
| 5–7 | **Adaptive ON** + **Start flash crowd** | Legitimate surge: many short connections. Adaptive rewrites `config` BPF map **without reload**. Threshold moves; false drops stay low. |
| 7–9 | **Adaptive OFF**, set threshold low (e.g. 50), flash crowd again | Static baseline wrongly drops legitimate surge — this is the FP contrast (novelty 3). |
| 9–10 | CLI | `python3 cli/ddosctl.py top` and `events` — same data as UI. |
| 10–11 | Optional Compass / Atlas | Show mirrored events if Atlas connected. |
| 11–12 | Eval file | `python3 eval/run_experiment.py --target <ip>` → open `eval/results/*.csv` / figure — thesis evidence. |

## Commands cheat-sheet

```bash
# Second terminal
python3 cli/ddosctl.py watch
python3 cli/ddosctl.py events

# Or manual traffic
sudo python3 attack/attack_gen.py --target <ip> --rate 250 --duration 20
python3 attack/flashcrowd_gen.py --target <ip> --rate 120 --duration 25
```

## If something fails

- No packets / no attach → Wi‑Fi: serve already falls back to SKB mode; prefer ethernet.
- Dashboard empty → confirm `serve.py` still running; browser hits correct host:port.
- Attack button does nothing → hping3 missing (`sudo apt install hping3`); script falls back to ping.
- Atlas OFF → fine for marks; detection does not depend on Mongo.
