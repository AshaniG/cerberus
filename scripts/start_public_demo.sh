#!/usr/bin/env bash
#
# start_public_demo.sh — start the full Cerberus system AND a public link, in one go.
#
# Run it in your OWN terminal (so it keeps running):
#     bash scripts/start_public_demo.sh
#
# Keep the window open. Press Ctrl+C to stop everything.

cd "$(dirname "$0")/.." || exit 1

# Auto-detect your main network interface (wifi or ethernet).
IFACE=$(ip -o -4 route show to default | awk '{print $5}' | head -1)
echo "==> Using network interface: $IFACE"

# Free port 8080 if something is already using it.
sudo fuser -k 8080/tcp 2>/dev/null || true
sleep 1

echo "==> Starting Cerberus (real kernel + dashboard). Kernel attach takes ~15s ..."
sudo python3 backend/serve.py "$IFACE" --threshold 500000 --no-adaptive \
     --host 0.0.0.0 --port 8080 > /tmp/cerberus_serve.log 2>&1 &

# Wait until the dashboard answers.
for i in $(seq 1 40); do
    if curl -s -o /dev/null http://127.0.0.1:8080/ 2>/dev/null; then
        echo "==> Cerberus is UP (dashboard running on localhost:8080)"
        break
    fi
    sleep 1
done

echo ""
echo "=================================================================="
echo "  Opening your PUBLIC LINK now."
echo "  Look below for a line like:  https://xxxxx.trycloudflare.com"
echo "  Copy that link into a browser or send it to your panel."
echo "  KEEP THIS WINDOW OPEN. Press Ctrl+C here to stop everything."
echo "=================================================================="
echo ""

cloudflared tunnel --url http://localhost:8080
