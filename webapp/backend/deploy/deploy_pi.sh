#!/usr/bin/env bash
set -euo pipefail

PI_IP="${1:-}"
if [[ -z "$PI_IP" ]]; then
  echo "Usage: $0 <PI_IP>"
  exit 1
fi

PI_USER="${PI_USER:-pi}"
REMOTE_DIR="${REMOTE_DIR:-/opt/ids2}"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

VERBOSE="${VERBOSE:-1}"
if [[ "$VERBOSE" == "1" ]]; then
  set -x
fi

SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10)
RSYNC_OPTS=(-avz --delete --exclude '__pycache__' --exclude '*.pyc' --exclude '.venv' --exclude 'dist')

echo "==> Create remote dir"
ssh -t "${SSH_OPTS[@]}" "${PI_USER}@${PI_IP}" \
  "sudo mkdir -p '${REMOTE_DIR}' && sudo chown -R '${PI_USER}':'${PI_USER}' '${REMOTE_DIR}'"

echo "==> Sync project"
rsync "${RSYNC_OPTS[@]}" -e "ssh ${SSH_OPTS[*]}" \
  "${LOCAL_DIR}/" "${PI_USER}@${PI_IP}:${REMOTE_DIR}/"

echo "==> Install deps (Docker/Suricata/etc.)"
ssh -t "${SSH_OPTS[@]}" "${PI_USER}@${PI_IP}" \
  "cd '${REMOTE_DIR}' && sudo bash deploy/install.sh"

echo "==> Generate docker/.env on Pi"
ssh "${SSH_OPTS[@]}" "${PI_USER}@${PI_IP}" \
  "python3 - <<'PY' '${REMOTE_DIR}/config.yaml' '${REMOTE_DIR}/secret.json' '${REMOTE_DIR}/docker/.env'
import json, os, sys
cfg_path, secret_path, env_path = sys.argv[1:4]

def load_yaml(path):
    try:
        import yaml
    except Exception:
        return {}
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

config = load_yaml(cfg_path)
secret = load_json(secret_path)

aws = config.get('aws', {}) if isinstance(config, dict) else {}
opensearch = aws.get('opensearch', {}) if isinstance(aws, dict) else {}
endpoint = aws.get('opensearch_endpoint') or opensearch.get('endpoint')
region = aws.get('region')

secret_aws = secret.get('aws', {}) if isinstance(secret, dict) else {}

lines = []
if secret_aws.get('access_key_id'):
    lines.append(f\"AWS_ACCESS_KEY_ID={secret_aws['access_key_id']}\")
if secret_aws.get('secret_access_key'):
    lines.append(f\"AWS_SECRET_ACCESS_KEY={secret_aws['secret_access_key']}\")
if region:
    lines.append(f\"AWS_REGION={region}\")
if endpoint:
    lines.append(f\"OPENSEARCH_ENDPOINT={endpoint}\")

os.makedirs(os.path.dirname(env_path), exist_ok=True)
if lines:
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write('\\n'.join(lines) + '\\n')
    print('docker/.env generated')
else:
    print('No variables written to docker/.env')
PY"

echo "==> Install systemd services"
ssh -t "${SSH_OPTS[@]}" "${PI_USER}@${PI_IP}" \
  "sudo cp '${REMOTE_DIR}/deploy/ids2-agent.service' /etc/systemd/system/ids2-agent.service && \
   sudo cp '${REMOTE_DIR}/deploy/suricata.service' /etc/systemd/system/suricata.service && \
   sudo systemctl daemon-reload"

echo "==> Start Docker stack"
ssh -t "${SSH_OPTS[@]}" "${PI_USER}@${PI_IP}" \
  "cd '${REMOTE_DIR}' && sudo DOCKER_BUILDKIT=1 docker build --network host -t ids2-fastapi:latest -f docker/fastapi/Dockerfile . && \
   cd '${REMOTE_DIR}/docker' && sudo docker compose up -d"

echo "==> Restart services"
ssh -t "${SSH_OPTS[@]}" "${PI_USER}@${PI_IP}" \
  "sudo systemctl restart suricata.service && sudo systemctl restart ids2-agent.service"

echo "==> Health check"
ssh "${SSH_OPTS[@]}" "${PI_USER}@${PI_IP}" \
  "curl -sS http://localhost:8080/health || true"

echo ""
echo "Endpoint: http://${PI_IP}:8080/health"
echo "Status:   http://${PI_IP}:8080/status"
