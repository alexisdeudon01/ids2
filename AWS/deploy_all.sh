#!/usr/bin/env bash
set -euo pipefail

# ============================================
# Master Deployment Script
# Déploie tout sur le Raspberry Pi via SSH
# ============================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $*"; }
success() { echo -e "${GREEN}✅ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }

echo ""
echo "╔════════════════════════════════════════════╗"
echo "║   IDS2 - Master Deployment Script         ║"
echo "║   Deploy to Raspberry Pi via SSH          ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# ============================================
# STEP 1: Extract AWS Data
# ============================================
log "STEP 1/3: Extracting AWS data..."
if [[ -f "$SCRIPT_DIR/extract_aws_data.sh" ]]; then
    bash "$SCRIPT_DIR/extract_aws_data.sh"
    success "AWS data extracted"
else
    warn "extract_aws_data.sh not found, skipping"
fi

echo ""

# ============================================
# STEP 2: Deploy Database (MySQL)
# ============================================
log "STEP 2/3: Deploying MySQL database to Pi..."
if [[ -f "$SCRIPT_DIR/deploy_db_to_pi.sh" ]]; then
    bash "$SCRIPT_DIR/deploy_db_to_pi.sh"
    success "MySQL database deployed"
else
    warn "deploy_db_to_pi.sh not found, skipping"
fi

echo ""

# ============================================
# STEP 3: Deploy Suricata IDS
# ============================================
log "STEP 3/3: Deploying Suricata IDS to Pi..."
if [[ -f "$SCRIPT_DIR/deploy_suricata_to_pi.sh" ]]; then
    bash "$SCRIPT_DIR/deploy_suricata_to_pi.sh"
    success "Suricata IDS deployed"
else
    warn "deploy_suricata_to_pi.sh not found, skipping"
fi

echo ""

# ============================================
# Summary
# ============================================
success "╔════════════════════════════════════════════╗"
success "║   Deployment Complete!                     ║"
success "╚════════════════════════════════════════════╝"
echo ""
log "What was deployed:"
log "  ✅ MySQL Database (with AWS data + ELK credentials)"
log "  ✅ Suricata IDS (monitoring network traffic)"
echo ""
log "Next steps:"
log "  1. Verify services:"
log "     ./monitor_db_coherence.py --once"
echo ""
log "  2. Start continuous monitoring:"
log "     ./monitor_db_coherence.py"
echo ""
log "  3. Connect to MySQL:"
log "     mysql -h 192.168.178.66 -P 3306 -uids_user -padmin ids_db"
echo ""
log "  4. Check Suricata logs:"
log "     ssh -i /home/tor/.ssh/pi_key pi@192.168.178.66 'sudo tail -f /var/log/suricata/eve.json'"
echo ""
