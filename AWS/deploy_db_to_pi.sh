#!/usr/bin/env bash
set -euo pipefail

# ============================================
# Deploy MySQL Database to Raspberry Pi
# ============================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/../config.json"

# Couleurs pour logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() { echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $*"; }
success() { echo -e "${GREEN}✅ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }
error() { echo -e "${RED}❌ $*${NC}" >&2; }

# Charger config.json
if [[ ! -f "$CONFIG_FILE" ]]; then
    error "Config file not found: $CONFIG_FILE"
    exit 1
fi

log "Loading configuration from $CONFIG_FILE..."
PI_HOST=$(jq -r '.pi_host // "sinik"' "$CONFIG_FILE")
PI_IP=$(jq -r '.pi_ip // "192.168.178.66"' "$CONFIG_FILE")
PI_USER=$(jq -r '.pi_user // "pi"' "$CONFIG_FILE")
PI_PASSWORD=$(jq -r '.pi_password // "pi"' "$CONFIG_FILE")
REMOTE_DIR=$(jq -r '.remote_dir // "/opt/ids2"' "$CONFIG_FILE")
SSH_KEY=$(jq -r '.ssh_key_path // "/home/tor/.ssh/pi_key"' "$CONFIG_FILE")

# Extract AWS data first
log "Extracting AWS data and generating SQL seeds..."
if [[ -f "$SCRIPT_DIR/extract_aws_data.sh" ]]; then
    bash "$SCRIPT_DIR/extract_aws_data.sh" || warn "Failed to extract AWS data, continuing anyway"
else
    warn "extract_aws_data.sh not found, skipping AWS data extraction"
fi

# Vérifier clé SSH
if [[ ! -f "$SSH_KEY" ]]; then
    error "SSH key not found: $SSH_KEY"
    exit 1
fi

PI_TARGET="${PI_IP}"
if [[ -z "$PI_IP" ]]; then
    PI_TARGET="${PI_HOST}"
fi

log "Target Pi: ${PI_USER}@${PI_TARGET}"
log "Remote directory: ${REMOTE_DIR}"

# Test connexion SSH
log "Testing SSH connection..."
if ! ssh -i "$SSH_KEY" -o ConnectTimeout=5 -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" "echo OK" &>/dev/null; then
    error "Cannot connect to Pi via SSH"
    error "Host: ${PI_TARGET}"
    error "User: ${PI_USER}"
    error "Key: ${SSH_KEY}"
    exit 1
fi
success "SSH connection OK"

# Créer répertoire distant pour DB
log "Creating remote database directory..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" \
    "sudo mkdir -p ${REMOTE_DIR}/mysql/data && sudo chown -R ${PI_USER}:${PI_USER} ${REMOTE_DIR}/mysql"
success "Remote directory created"

# Copier Dockerfile MySQL
log "Copying MySQL Dockerfile..."
scp -i "$SSH_KEY" -o StrictHostKeyChecking=no \
    "$SCRIPT_DIR/mysql/Dockerfile" \
    "${PI_USER}@${PI_TARGET}:${REMOTE_DIR}/mysql/"
success "Dockerfile copied"

# Copier init.sql
log "Copying MySQL init script..."
scp -i "$SSH_KEY" -o StrictHostKeyChecking=no \
    "$SCRIPT_DIR/mysql/init.sql" \
    "${PI_USER}@${PI_TARGET}:${REMOTE_DIR}/mysql/"
success "init.sql copied"

# Copier les fichiers SQL de données
if ls "$SCRIPT_DIR/datas"/*.sql >/dev/null 2>&1; then
    log "Copying SQL data files..."
    scp -i "$SSH_KEY" -o StrictHostKeyChecking=no \
        "$SCRIPT_DIR/datas"/*.sql \
        "${PI_USER}@${PI_TARGET}:${REMOTE_DIR}/mysql/" 2>/dev/null || warn "No SQL data files to copy"
    success "SQL data files copied"
else
    warn "No SQL data files found in $SCRIPT_DIR/datas/"
fi

# Créer docker-compose.yml pour MySQL sur Pi
log "Creating docker-compose.yml for MySQL..."
cat > /tmp/docker-compose-mysql.yml <<'EOF'
version: '3.8'

services:
  mysql:
    build:
      context: ./mysql
      dockerfile: Dockerfile
    container_name: ids2-mysql
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: ids_db
      MYSQL_USER: ids_user
      MYSQL_PASSWORD: admin
    ports:
      - "3306:3306"
    volumes:
      - ./mysql/data:/var/lib/mysql
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-uroot", "-proot"]
      interval: 10s
      timeout: 5s
      retries: 5
EOF

scp -i "$SSH_KEY" -o StrictHostKeyChecking=no \
    /tmp/docker-compose-mysql.yml \
    "${PI_USER}@${PI_TARGET}:${REMOTE_DIR}/docker-compose-mysql.yml"
success "docker-compose.yml copied"

# Vérifier si Docker est installé sur Pi
log "Checking Docker installation on Pi..."
if ! ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" "command -v docker &>/dev/null"; then
    warn "Docker not installed on Pi"
    log "Installing Docker..."
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" \
        "curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker ${PI_USER}"
    success "Docker installed"
    warn "Please logout and login again on Pi for docker group to take effect"
else
    success "Docker already installed"
fi

# Vérifier docker-compose
log "Checking docker-compose..."
if ! ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" "command -v docker-compose &>/dev/null"; then
    warn "docker-compose not installed"
    log "Installing docker-compose..."
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" \
        "sudo apt-get update && sudo apt-get install -y docker-compose"
    success "docker-compose installed"
else
    success "docker-compose already installed"
fi

# Build et démarrer MySQL container sur Pi
log "Building MySQL container on Pi..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" \
    "cd ${REMOTE_DIR} && sudo docker-compose -f docker-compose-mysql.yml build"
success "MySQL container built"

log "Starting MySQL container on Pi..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" \
    "cd ${REMOTE_DIR} && sudo docker-compose -f docker-compose-mysql.yml up -d"
success "MySQL container started"

# Attendre que MySQL soit prêt
log "Waiting for MySQL to be ready..."
for i in {1..30}; do
    if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" \
        "sudo docker exec ids2-mysql mysqladmin ping -h localhost -uroot -proot &>/dev/null"; then
        success "MySQL is ready!"
        break
    fi
    echo -n "."
    sleep 2
done
echo ""

# Vérifier les bases de données
log "Verifying databases..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" \
    "sudo docker exec ids2-mysql mysql -uids_user -padmin -e 'SHOW DATABASES;'"

# Vérifier les tables
log "Verifying tables..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${PI_USER}@${PI_TARGET}" \
    "sudo docker exec ids2-mysql mysql -uids_user -padmin ids_db -e 'SHOW TABLES;'"

success "============================================"
success "MySQL Database deployed successfully on Pi!"
success "============================================"
echo ""
log "Connection info:"
log "  Host: ${PI_TARGET}:3306"
log "  Database: ids_db"
log "  User: ids_user"
log "  Password: admin"
echo ""
log "To connect from local:"
log "  mysql -h ${PI_TARGET} -P 3306 -uids_user -padmin ids_db"
echo ""
log "To view logs:"
log "  ssh -i $SSH_KEY ${PI_USER}@${PI_TARGET} 'sudo docker logs ids2-mysql'"
