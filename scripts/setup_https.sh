#!/bin/bash
# Setup HTTPS for Social Maker Dashboard
# This installs Caddy and configures it to proxy app.nextframesmedia.com to port 8501

set -e

echo "============================================"
echo "  Social Maker HTTPS Setup"
echo "============================================"
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo: sudo ./setup_https.sh"
    exit 1
fi

# Step 1: Install Caddy
echo "[1/4] Installing Caddy..."
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl > /dev/null 2>&1

curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg 2>/dev/null

curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list > /dev/null

apt update > /dev/null 2>&1
apt install -y caddy > /dev/null 2>&1

echo "  Caddy installed!"

# Step 2: Backup existing Caddyfile if exists
echo "[2/4] Configuring Caddy..."
if [ -f /etc/caddy/Caddyfile ]; then
    cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.backup
    echo "  Backed up existing Caddyfile"
fi

# Step 3: Create Caddyfile
cat > /etc/caddy/Caddyfile << 'EOF'
# Social Maker Dashboard
app.nextframesmedia.com {
    reverse_proxy localhost:8501
}

# Open WebUI (if running)
# chat.nextframesmedia.com {
#     reverse_proxy localhost:3000
# }
EOF

echo "  Caddyfile configured for app.nextframesmedia.com"

# Step 4: Open firewall ports
echo "[3/4] Opening firewall ports..."
ufw allow 80 > /dev/null 2>&1 || true
ufw allow 443 > /dev/null 2>&1 || true
echo "  Ports 80 and 443 opened"

# Step 5: Start Caddy
echo "[4/4] Starting Caddy..."
systemctl enable caddy > /dev/null 2>&1
systemctl restart caddy

echo ""
echo "============================================"
echo "  Setup Complete!"
echo "============================================"
echo ""
echo "  IMPORTANT: Add this DNS record first:"
echo ""
echo "    Type: A"
echo "    Name: app"
echo "    Value: $(curl -s -4 ifconfig.me 2>/dev/null || echo 'YOUR_IP')"
echo ""
echo "  Then access your dashboard at:"
echo "    https://app.nextframesmedia.com"
echo ""
echo "  Speech input will work once DNS propagates!"
echo ""
echo "============================================"
