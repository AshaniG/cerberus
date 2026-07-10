# Cerberus — setup guide (development environment)

> Follow this top to bottom. Do not skip the verification checks — each confirms
> a layer works before you build on it. The point is to hit problems early, not
> in week six.

---

## 0. Which Ubuntu version (read this first)

Install **Ubuntu 24.04 LTS (Noble Numbat)** — NOT the newest 26.04 LTS.

Reasoning: 26.04 (released April 2026) ships with the brand-new Linux kernel 7.0.
The eBPF toolchain (BCC especially) is finicky about kernel versions, and on a
just-released kernel you risk being among the first to hit a fresh
BCC-vs-kernel incompatibility — exactly the setup rabbit hole a beginner on a
deadline must avoid. Ubuntu 24.04 has had two years of stabilisation, and the
overwhelming majority of current eBPF tutorials and Stack Overflow answers target
it. Stability and documentation matter more here than the newest kernel.

If your hardware *forces* a newer release, it can still work — but expect more
setup friction and tell me your exact kernel version so we adapt.

---

## 1. Install Ubuntu 24.04 LTS (bare metal / dual boot)

1. On Windows, download the **Ubuntu 24.04 LTS Desktop** ISO from
   `https://releases.ubuntu.com/24.04/`.
2. Create a bootable USB with **Rufus** (`https://rufus.ie`) or **balenaEtcher**.
3. Back up anything important on Windows first — dual-boot resizing touches disk
   partitions.
4. Boot from the USB (usually F12/F2/DEL at startup to pick the boot device).
5. Choose **"Install Ubuntu alongside Windows Boot Manager"** for dual boot. Give
   Ubuntu at least **40–50 GB** (CIC-IDS-2017 and tooling need room).
6. Finish, reboot, log into Ubuntu.

> Modern Ubuntu uses Wayland by default and `sudo` may show asterisks as you type
> your password — both normal, not errors.

---

## 2. First-boot basics

```bash
sudo apt update && sudo apt upgrade -y
```

Record your exact versions (paste these to me for M0 — they determine the exact
eBPF approach):

```bash
lsb_release -a      # Ubuntu version
uname -r            # kernel version
```

---

## 3. Install the eBPF / BCC toolchain

BCC compiles your eBPF C on the machine, so it needs kernel headers + compiler.

```bash
sudo apt install -y \
  bpfcc-tools \
  libbpfcc \
  libbpfcc-dev \
  linux-headers-$(uname -r) \
  python3-bpfcc \
  clang \
  llvm \
  libelf-dev \
  build-essential \
  linux-tools-common \
  linux-tools-$(uname -r)
```

What these are:
- `bpfcc-tools`, `libbpfcc*`, `python3-bpfcc` — BCC and its Python bindings.
- `linux-headers-$(uname -r)` — kernel headers matching your running kernel; BCC
  needs these to compile eBPF. If this exact package isn't found, that mismatch is
  a classic setup snag — tell me the error.
- `clang`, `llvm` — the compiler backend BCC uses to build eBPF bytecode.
- `libelf-dev`, `build-essential` — supporting build libraries.
- `linux-tools-*` — includes `bpftool`, for inspecting loaded programs/maps.

---

## 4. Install traffic + Python tooling

```bash
sudo apt install -y hping3                 # attack traffic generator
sudo apt install -y python3-pip python3-venv git
sudo apt install -y sqlite3                # optional, inspect the DB by hand
```

Python libraries for Tier-2 ML/analysis (installed at M5 into the project venv):
`scikit-learn`, `pandas`, `numpy`, `joblib`. BCC's Python binding is installed
system-wide via `python3-bpfcc` above and used with the system Python; the venv
is only for the ML/analysis side.

---

## 5. Install Claude Code

```bash
sudo apt install -y nodejs npm    # Claude Code needs Node.js
```

Then install Claude Code using the current official instructions at
`https://docs.claude.com` (the exact command changes over time — check the docs
rather than trusting a hard-coded line). Run it from inside the `cerberus/` folder
(see §7) so it picks up `docs/PROJECT_CONTEXT.md` automatically.

---

## 6. Verification checks (do not skip)

**Check A — kernel supports eBPF/XDP:**
```bash
uname -r          # any 6.x kernel is fine for XDP
```

**Check B — BCC importable from Python:**
```bash
python3 -c "from bcc import BPF; print('BCC OK')"
# Expect: BCC OK  — if it errors, the §3 install didn't complete; fix first.
```

**Check C — bpftool works:**
```bash
sudo bpftool version
```

**Check D — find your network interface name (needed to attach XDP):**
```bash
ip link show
# Note your main interface, e.g. enp3s0, eth0, wlan0.
# Wi-Fi (wlan*) often lacks good native XDP support — prefer a wired interface.
# If you must use Wi-Fi, we'll use generic/SKB XDP mode.
```

**Check E — hping3 present:**
```bash
hping3 --version
```

If A–E all pass, your environment is ready and most project risk is gone.

---

## 7. Create the repo and drop in the docs

```bash
mkdir -p ~/cerberus
cd ~/cerberus
git init
```

Put `PROJECT_CONTEXT.md`, `SETUP_GUIDE.md`, and `FOLDER_LAYOUT.md` into a `docs/`
folder inside the repo, and the `README.md` + `.gitignore` at the root. Then open
Claude Code from inside `~/cerberus` so it reads the context automatically.

---

## 8. What to send me when setup is done

Paste back:
1. Output of `lsb_release -a` and `uname -r`.
2. Whether Check B (`BCC OK`) passed.
3. Your network interface name from Check D (wired or Wi-Fi).

With those three, I'll give you the M0 program (hello-eBPF) and its BCC loader,
fully commented and explained line by line, ready to run.
