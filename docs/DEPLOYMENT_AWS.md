+# Hosting Cerberus on AWS (step by step, for beginners)

This hosts the **full** Cerberus system (real kernel data + dashboard) on an AWS server
that runs 24/7. Work through it one stage at a time. Take your time.

> AWS EC2 uses a virtual network card, so XDP attaches in **generic/SKB mode** (still real
> kernel filtering, just not native mode). `serve.py` handles this automatically.

---

## STAGE 1 — Create an AWS account (once)

1. Go to **https://aws.amazon.com/free**
2. Click **"Create a Free Account"**
3. Enter your email, a password, and an account name (e.g. `cerberus`)
4. It asks for a **credit/debit card** — this is for verification. The **Free Tier** is
   free for 12 months if you stay on the small instance below.
5. Verify your phone number (they send a code)
6. Choose the **Basic support - Free** plan
7. Finish and sign in to the **AWS Management Console**

---

## STAGE 2 — Launch a server (EC2 instance)

1. At the top search bar, type **EC2** and click **EC2**
2. Make sure the **Region** (top-right) is one near you (e.g. *Mumbai ap-south-1*)
3. Click the orange **"Launch instance"** button
4. Fill in:
   - **Name:** `cerberus`
   - **Application and OS Image:** choose **Ubuntu** (Ubuntu Server 24.04 LTS) — make sure
     it says **"Free tier eligible"**
   - **Instance type:** choose **t2.micro** or **t3.micro** (must say **"Free tier eligible"**)
5. **Key pair (login):** click **"Create new key pair"**
   - Name: `cerberus-key`
   - Type: RSA, Format: **.pem**
   - Click **Create key pair** → a file `cerberus-key.pem` downloads. **KEEP THIS FILE
     SAFE** — it is your password to the server.
6. **Network settings** → click **Edit**, and tick these boxes (Allow ... from Anywhere):
   - **Allow SSH traffic** (port 22) — usually on by default
   - **Allow HTTP traffic** — tick it
   - Then add one custom rule for the dashboard (see Stage 3)
7. Click **"Launch instance"**
8. Click **"View all instances"** — wait until **Instance state = Running** and note the
   **Public IPv4 address** (e.g. `13.201.x.x`)

---

## STAGE 3 — Open the dashboard port (8080)

1. In EC2, left menu → **Security Groups**
2. Click the security group attached to your instance
3. Tab **"Inbound rules"** → **Edit inbound rules** → **Add rule**:
   - Type: **Custom TCP**
   - Port range: **8080**
   - Source: **Anywhere-IPv4 (0.0.0.0/0)**
4. Click **Save rules**

---

## STAGE 4 — Connect to your server (SSH)

On **your own laptop**, open a terminal in the folder where `cerberus-key.pem` downloaded
(usually Downloads), then:

```bash
cd ~/Downloads
chmod 400 cerberus-key.pem
ssh -i cerberus-key.pem ubuntu@<YOUR-PUBLIC-IP>
```
Type **yes** if it asks about authenticity. You are now "inside" the server.

---

## STAGE 5 — Install and run Cerberus (on the server)

```bash
git clone https://github.com/AshaniG/cerberus.git
cd cerberus
bash scripts/vps_setup.sh
```
This installs the eBPF toolchain and Python deps (takes a few minutes). It prints your
interface name at the end (often `ens5` on AWS).

Add MongoDB (optional):
```bash
cp .env.example .env
nano .env         # paste your MONGODB_URI, then Ctrl+O, Enter, Ctrl+X
```

Start it (use the interface name printed above):
```bash
sudo python3 backend/serve.py ens5 --host 0.0.0.0 --port 8080
```
Wait for `Attached ...` and `Dashboard: http://0.0.0.0:8080/`.

---

## STAGE 6 — Open your dashboard

In any browser:
```
http://<YOUR-PUBLIC-IP>:8080
```
That is your live system, hosted on AWS, reachable from anywhere. 🎉

---

## STAGE 7 (optional) — Keep it running 24/7

See `scripts/cerberus.service` and Step 9 in `docs/DEPLOYMENT.md`.

---

## Show a real attack (from your laptop)
```bash
sudo hping3 -S -p 80 -i u2000 <YOUR-PUBLIC-IP>
```
Watch the dashboard's DROPPED counter climb once it crosses the threshold.

## Cost warning
- The **t2.micro / t3.micro** instance is **free for 12 months**.
- **STOP or TERMINATE the instance** in the EC2 console when you are done, so you are not
  charged later. (Terminate = delete it completely.)
