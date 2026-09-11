#!/usr/bin/env bash
#
# vps_setup.sh — one-shot setup for hosting Cerberus on a fresh Ubuntu cloud VM.
# Installs the eBPF/BCC toolchain + Python deps so `serve.py` can attach XDP.
#
# Run ON THE VM (Ubuntu 22.04 or 24.04), from the project root, as a normal user:
#     bash scripts/vps_setup.sh
#
set -e

echo "==> 1/4  Updating package list and installing eBPF/BCC toolchain ..."
sudo apt-get update
sudo apt-get install -y \
    python3-bpfcc bpfcc-tools libbpfcc \
    linux-headers-"$(uname -r)" \
    clang llvm \
    python3-pip git

echo "==> 2/4  Installing Python project dependencies ..."
# Ubuntu 24.04 marks the system Python "externally managed"; --break-system-packages
# installs into the same interpreter BCC uses, which is what serve.py needs.
sudo pip3 install -r requirements.txt --break-system-packages || \
    sudo pip3 install -r requirements.txt

echo "==> 3/4  Checking the BCC toolchain works ..."
python3 -c "from bcc import BPF; print('    BCC OK')"

echo "==> 4/4  Detecting your network interface ..."
IFACE=$(ip -o -4 route show to default | awk '{print $5}' | head -1)
echo "    Your main interface looks like: ${IFACE:-<not found, run: ip link>}"

echo ""
echo "=================================================================="
echo " Setup done. Next:"
echo "   1) Create your .env   (copy .env.example -> .env, add MONGODB_URI)"
echo "   2) Open port 8080 in your cloud provider's firewall/security group"
echo "   3) sudo ufw allow 8080/tcp   (if ufw is on)"
echo "   4) Start it:"
echo "        sudo python3 backend/serve.py ${IFACE:-<iface>} --host 0.0.0.0 --port 8080"
echo "   5) Open   http://<your-VM-public-IP>:8080"
echo "=================================================================="
