# How to Run Cerberus Yourself (simple guide)

Everything you need to run, demo, and host your project — written so you can do it
without help. Run all commands from the project folder:

```bash
cd ~/Projects/cerberus
```

---

## 1. Run the full system (real kernel data + dashboard)

```bash
sudo python3 backend/serve.py wlo1 --host 0.0.0.0 --port 8080
```
- Replace `wlo1` with your interface if different — find it with: `ip route | grep default`
- Then open **http://localhost:8080** in your browser
- Stop it with **Ctrl + C**

> If the dashboard shows "No response" errors, your filter is dropping normal traffic.
> Fix: on the dashboard click **Adaptive OFF**, set **Threshold = 500000**, click **Set**,
> then **Clear counters**.

---

## 2. Get a public link (so others can see it)

Start the system (step 1) in one terminal, then in a **second** terminal:
```bash
cloudflared tunnel --url http://localhost:8080
```
It prints a link like `https://xxxx.trycloudflare.com`. Open that in any browser or share
it. Keep the terminal open; Ctrl + C closes the link.

**Shortcut:** do both at once with:
```bash
bash scripts/start_public_demo.sh
```

---

## 3. Show a real attack (for your demo)

On the dashboard:
1. Click **Clear counters**
2. Set **Threshold = 1000** → **Set**
3. Click **Start attack**
4. Watch **DROPPED** climb and the attacker IP turn red in "Top sources"
5. Click **Stop attack**, then **Clear counters** when done

---

## 4. Use the command-line tool

```bash
ddosctl status      # system status
ddosctl top         # top source IPs
ddosctl attack      # is an attack happening now?
ddosctl events      # recent events
```
(If `ddosctl` is not found, run `bash cli/install.sh` once, then open a new terminal.)

---

## 5. Re-train the ML model (if needed)

```bash
python3 ml/train_tree.py
```
Uses the CIC-IDS-2017 data in `data/cic-ids-2017/`. Prints accuracy (~0.86) and saves
`ml/model/tree.joblib`.

---

## 6. Your documents

- **Final thesis:** `docs/final_thesis/Final_Thesis.pdf` (and `.docx`)
- **Interim report:** `docs/interim_report/Interim_Report.pdf`
- Copies are also in your `~/Downloads/` folder.

---

## 7. Host it online 24/7 (advanced, optional)

- On any cloud: see `docs/DEPLOYMENT.md`
- On AWS specifically: see `docs/DEPLOYMENT_AWS.md`

---

## 8. Save future changes to GitHub

```bash
git add -A
git commit -m "describe your change"
git push
```

---

## Key facts (for your viva / report)

- **What it is:** a kernel-level network security system (NOT a web app or mobile app),
  built on eBPF/XDP, for DDoS detection.
- **Languages:** C (kernel filter) + Python (everything in userspace); the dashboard uses
  HTML/CSS/JavaScript.
- **Three novelties:** (1) adaptive threshold updated live with no XDP reload;
  (2) selective ML escalation — the classifier runs only on ambiguous traffic;
  (3) flash-crowd false-positive evaluation.
- **Real results:** 0.86 classifier accuracy on 702,718 CIC-IDS-2017 samples; in the
  flash-crowd test the static threshold blocked all 12 legitimate users while the adaptive
  one blocked 0 — both caught the attacker.
- **MongoDB:** optional cloud mirror; the system works fully without it (uses local SQLite).
