#!/bin/bash
# Setup script for IDS Dashboard on Raspberry Pi

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🚀 Setting up IDS Dashboard on Raspberry Pi..."

# Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    suricata \
    docker.io \
    docker-compose

# Install Suricata rules
echo "📥 Updating Suricata rules..."
sudo suricata-update

# Enable promiscuous mode on eth0
echo "🔧 Configuring network interface..."
sudo ip link set eth0 promisc on

# Create virtual environment if it doesn't exist
if [ ! -d "${ROOT_DIR}/.venv" ]; then
    echo "🐍 Creating Python virtual environment..."
    python3 -m venv "${ROOT_DIR}/.venv"
fi

# Activate virtual environment
source "${ROOT_DIR}/.venv/bin/activate"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r "${ROOT_DIR}/requirements.txt"

# Create necessary directories
echo "📁 Creating directories..."
sudo mkdir -p /var/log/suricata
sudo chown -R $USER:$USER /var/log/suricata

# Setup Suricata configuration
if [ ! -f "/etc/suricata/suricata.yaml" ]; then
    echo "⚠️  Suricata configuration not found. Please configure /etc/suricata/suricata.yaml"
fi

# Setup environment variables
echo "📝 Setting up environment variables..."
if [ ! -f "${ROOT_DIR}/.env" ]; then
    cat > "${ROOT_DIR}/.env" << EOF
# Dashboard Configuration
DASHBOARD_PORT=8080
MIRROR_INTERFACE=eth0
LED_PIN=17

# Elasticsearch
ELASTICSEARCH_HOSTS=http://localhost:9200
ELASTICSEARCH_USERNAME=
ELASTICSEARCH_PASSWORD=

# Tailscale
TAILSCALE_TAILNET=
TAILSCALE_API_KEY=

# Anthropic AI Healing
ANTHROPIC_API_KEY=
EOF
    echo "✅ Created .env file. Please update with your configuration."
fi

# Create systemd service
echo "🔧 Creating systemd service..."
sudo tee /etc/systemd/system/ids-dashboard.service > /dev/null << EOF
[Unit]
Description=IDS Dashboard
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=${ROOT_DIR}
Environment="PATH=${ROOT_DIR}/.venv/bin"
ExecStart=${ROOT_DIR}/.venv/bin/python -m ids.dashboard.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your configuration"
echo "2. Start the dashboard: sudo systemctl start ids-dashboard"
echo "3. Enable auto-start: sudo systemctl enable ids-dashboard"
echo "4. View logs: sudo journalctl -u ids-dashboard -f"
echo ""
echo "Or run manually:"
echo "  source ${ROOT_DIR}/.venv/bin/activate"
echo "  python -m ids.dashboard.main"
