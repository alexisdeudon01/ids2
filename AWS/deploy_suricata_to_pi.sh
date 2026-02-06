#!/usr/bin/env bash
set -euo pipefail

# ============================================
# Deploy Suricata IDS to Raspberry Pi
# ============================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/../config.json"

# Couleurs pour logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $*"; }
success() { echo -e "${GREEN}✅ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }
error() { echo -e "${RED}❌ $*${NC}" >&2; }

# Charger config
if [[ ! -f "$CONFIG_FILE" ]]; then
    error "Config file not found: $CONFIG_FILE"
    exit 1
fi

log "Loading configuration..."
PI_HOST=$(jq -r '.pi_host // "sinik"' "$CONFIG_FILE")
PI_IP=$(jq -r '.pi_ip // "192.168.178.66"' "$CONFIG_FILE")
PI_USER=$(jq -r '.pi_user // "pi"' "$CONFIG_FILE")
REMOTE_DIR=$(jq -r '.remote_dir // "/opt/ids2"' "$CONFIG_FILE")
MIRROR_INTERFACE=$(jq -r '.mirror_interface // "eth0"' "$CONFIG_FILE")
SSH_KEY=$(jq -r '.ssh_key_path // "/home/tor/.ssh/pi_key"' "$CONFIG_FILE")

PI_TARGET="${PI_IP}"
[[ -z "$PI_IP" ]] && PI_TARGET="${PI_HOST}"

log "Target: ${PI_USER}@${PI_TARGET}"
log "Mirror interface: ${MIRROR_INTERFACE}"

# Test SSH
log "Testing SSH connection..."
if ! ssh -i "$SSH_KEY" -o ConnectTimeout=5 -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" "echo OK" &>/dev/null; then
    error "Cannot connect to Pi via SSH"
    exit 1
fi
success "SSH connection OK"

# ============================================
# Installation Suricata
# ============================================
log "Installing Suricata IDS on Pi..."

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" bash <<'REMOTE_SCRIPT'
set -euo pipefail

echo "📦 Updating package list..."
sudo apt-get update -qq

echo "🛡️ Installing Suricata..."
sudo apt-get install -y suricata

echo "📥 Updating Suricata rules..."
sudo suricata-update

echo "✅ Suricata installed"

# Vérifier version
SURICATA_VERSION=$(suricata --version | head -n1)
echo "📊 Suricata version: $SURICATA_VERSION"
REMOTE_SCRIPT

success "Suricata installed"

# ============================================
# Configuration Suricata
# ============================================
log "Configuring Suricata..."

# Créer répertoire pour logs
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" \
    "sudo mkdir -p /var/log/suricata && sudo chown -R ${PI_USER}:${PI_USER} /var/log/suricata"

# Configuration yaml
cat > /tmp/suricata-config.yaml <<EOF
%YAML 1.1
---
vars:
  address-groups:
    HOME_NET: "[192.168.0.0/16,10.0.0.0/8,172.16.0.0/12]"
    EXTERNAL_NET: "!\\$HOME_NET"

af-packet:
  - interface: ${MIRROR_INTERFACE}
    threads: auto
    cluster-id: 99
    cluster-type: cluster_flow
    defrag: yes
    use-mmap: yes
    tpacket-v3: yes

outputs:
  - eve-log:
      enabled: yes
      filetype: regular
      filename: /var/log/suricata/eve.json
      types:
        - alert:
            payload: yes
            http: yes
            tls: yes
            ssh: yes
            smtp: yes
        - http:
            extended: yes
        - dns:
            query: yes
            answer: yes
        - tls:
            extended: yes
        - files:
            force-magic: no
        - smtp:
        - ssh
        - stats:
            totals: yes
            threads: no
            deltas: no
        - flow

logging:
  default-log-level: info
  outputs:
    - console:
        enabled: yes
    - file:
        enabled: yes
        filename: /var/log/suricata/suricata.log

pcap-file:
  checksum-checks: auto
EOF

scp -i "$SSH_KEY" -o StrictHostKeyChecking=no /tmp/suricata-config.yaml "${PI_USER}@${PI_TARGET}:/tmp/"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" \
    "sudo mv /tmp/suricata-config.yaml /etc/suricata/suricata.yaml"

success "Suricata configured"

# ============================================
# Créer service systemd
# ============================================
log "Creating Suricata systemd service..."

cat > /tmp/suricata.service <<EOF
[Unit]
Description=Suricata Intrusion Detection Service
After=network.target

[Service]
Type=simple
ExecStartPre=/bin/sleep 5
ExecStart=/usr/bin/suricata -c /etc/suricata/suricata.yaml --af-packet=${MIRROR_INTERFACE}
ExecReload=/bin/kill -USR2 \$MAINPID
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

scp -i "$SSH_KEY" -o StrictHostKeyChecking=no /tmp/suricata.service "${PI_USER}@${PI_TARGET}:/tmp/"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" bash <<'REMOTE'
sudo mv /tmp/suricata.service /etc/systemd/system/suricata.service
sudo systemctl daemon-reload
sudo systemctl enable suricata
sudo systemctl restart suricata
REMOTE

success "Suricata service configured and started"

# ============================================
# Vérification
# ============================================
log "Verifying Suricata status..."
sleep 3

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" \
    "sudo systemctl status suricata --no-pager || true"

# Check logs
log "Checking Suricata logs..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" \
    "sudo tail -n 10 /var/log/suricata/suricata.log || echo 'No logs yet'"

# Check interface
log "Checking network interface ${MIRROR_INTERFACE}..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" \
    "ip addr show ${MIRROR_INTERFACE} || warn 'Interface not found'"

# ============================================
# Summary
# ============================================
echo ""
success "============================================"
success "Suricata IDS deployed successfully on Pi!"
success "============================================"
echo ""
log "Monitor interface: ${MIRROR_INTERFACE}"
log "Logs directory: /var/log/suricata/"
log "Eve JSON log: /var/log/suricata/eve.json"
echo ""
log "Useful commands:"
log "  Status: ssh -i $SSH_KEY ${PI_USER}@${PI_TARGET} 'sudo systemctl status suricata'"
log "  Logs: ssh -i $SSH_KEY ${PI_USER}@${PI_TARGET} 'sudo tail -f /var/log/suricata/suricata.log'"
log "  Alerts: ssh -i $SSH_KEY ${PI_USER}@${PI_TARGET} 'sudo tail -f /var/log/suricata/eve.json | jq select(.event_type==\"alert\")'"
echo ""
