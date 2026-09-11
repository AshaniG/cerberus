# Hosting Cerberus (full system, real kernel data, always on)

This guide hosts the **complete** Cerberus system — the real eBPF/XDP kernel filter,
the dashboard, the ML tier, and MongoDB — on a cloud server, reachable at a public
address 24/7.

Because Cerberus runs **inside the Linux kernel**, it needs a **cloud VM (VPS)** where
you have **root access**. Free web hosts (Netlify, Vercel, Render, Heroku) cannot run it.

> **Note on XDP mode:** on most cloud VMs the network card is virtual, so XDP usually
> attaches in **generic/SKB mode** rather than native mode. This is still real, in-kernel
> packet filtering — just not the fastest driver-level path. `serve.py` falls back to SKB
> mode automatically, so no change is needed.

---

## Step 1 — Create a cloud VM

Pick one provider and create an **Ubuntu 22.04 or 24.04** server:

| Provider | Cost | Notes |
|---|---|---|
| **Oracle Cloud Free Tier** | Free, always on | Best free option; sign-up needs a card for verification |
| **AWS EC2** (t3.micro) | Free for 12 months | Student credits often available |
| **Hetzner / DigitalOcean / Vultr / Linode** | ~$4–6 / month | Simplest and most reliable |

When creating it:
- Image: **Ubuntu 24.04 LTS** (or 22.04)
- Size: the smallest is fine (1 vCPU, 1 GB RAM)
- **Save the SSH key / password** it gives you
- Note the server's **public IP address**

## Step 2 — Open the firewall for the dashboard

In your provider's control panel (Security Group / Firewall rules), allow inbound:
- **TCP 22** (SSH — usually already open)
- **TCP 8080** (the dashboard)

## Step 3 — Connect to the VM

From your own computer's terminal:
```bash
ssh ubuntu@<your-VM-public-IP>
```
(the username may be `ubuntu`, `root`, or `opc` depending on the provider)

## Step 4 — Get the project onto the VM

```bash
git clone https://github.com/AshaniG/cerberus.git
cd cerberus
```

## Step 5 — Install everything (one command)

```bash
bash scripts/vps_setup.sh
```
This installs the eBPF/BCC toolchain, the kernel headers, and the Python dependencies,
then checks BCC works and prints your network interface name (e.g. `ens3` or `eth0`).

## Step 6 — Add your MongoDB connection

```bash
cp .env.example .env
nano .env          # paste your MONGODB_URI, save with Ctrl+O then Ctrl+X
```

## Step 7 — Start the full system

Use the interface name that Step 5 printed (here shown as `ens3`):
```bash
sudo ufw allow 8080/tcp            # only if the ufw firewall is on
sudo python3 backend/serve.py ens3 --host 0.0.0.0 --port 8080
```
You should see: `Attached to ens3 ...`, `MongoDB Atlas: connected`, and
`Dashboard: http://0.0.0.0:8080/`.

## Step 8 — Open your dashboard

In any browser:
```
http://<your-VM-public-IP>:8080
```
This is your live system with **real kernel data**, reachable from anywhere. 🎉

---

## Step 9 (optional) — Keep it running 24/7 (survives logout + reboot)

Running it by hand stops when you close the SSH window. To keep it always on:

```bash
sudo cp scripts/cerberus.service /etc/systemd/system/cerberus.service
sudo nano /etc/systemd/system/cerberus.service   # fix WorkingDirectory + interface name
sudo systemctl daemon-reload
sudo systemctl enable --now cerberus
sudo systemctl status cerberus                    # confirm it is running
```

## Step 10 (optional) — Use a domain name (cerberus.something)

1. Buy/register a domain (or use a free one from a service like DuckDNS).
2. In your domain's DNS settings, add an **A record** pointing your name to the VM's
   public IP.
3. It will then answer at `http://your-name.com:8080`. (Serving it on port 80/443 with
   HTTPS needs a reverse proxy such as Nginx + a free Let's Encrypt certificate — a good
   later step, not required for a demo.)

---

## Showing a REAL attack against the hosted system

This is the nice part: from **your own laptop**, send attack traffic to the VM's public
IP. Because it travels over the real network, the VM's kernel genuinely sees and filters
it (this is what a single machine could not do on its own):

```bash
# on your laptop (install hping3 first: sudo apt install hping3)
sudo hping3 -S -p 80 -i u2000 <your-VM-public-IP>
```
Watch the dashboard's **DROPPED** counter climb and the attacker's IP turn red once it
crosses the threshold. Stop with Ctrl+C.

---

## Honest limitations to keep in mind

- On a cloud VM, XDP runs in **generic/SKB mode** (still real, just not native driver
  mode) — this matches the single-host limitation already noted in the dissertation.
- The VM only sees traffic actually sent to it, so "real data" means the VM's own traffic
  plus whatever test traffic you send it — which is exactly what you want for a controlled
  demonstration.
