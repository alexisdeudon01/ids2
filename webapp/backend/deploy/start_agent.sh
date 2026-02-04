#!/bin/bash

# Script pour démarrer le service systemd de l'agent IDS2 SOC et afficher ses logs.

echo "Démarrage du service Suricata..."
sudo systemctl start suricata.service

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

SECRET_FILE="$ROOT_DIR/secret.json"
CONFIG_FILE="$ROOT_DIR/config.yaml"

if [ -f "$SECRET_FILE" ]; then
  AWS_ACCESS_KEY_ID="$(python3 - <<'PY' "$SECRET_FILE"
import json, sys
try:
    data = json.load(open(sys.argv[1], "r", encoding="utf-8"))
    print(data.get("aws", {}).get("access_key_id", ""))
except Exception:
    print("")
PY
)"
  AWS_SECRET_ACCESS_KEY="$(python3 - <<'PY' "$SECRET_FILE"
import json, sys
try:
    data = json.load(open(sys.argv[1], "r", encoding="utf-8"))
    print(data.get("aws", {}).get("secret_access_key", ""))
except Exception:
    print("")
PY
)"
fi

if [ -f "$CONFIG_FILE" ]; then
  if [ -z "$AWS_REGION" ]; then
    AWS_REGION="$(python3 - <<'PY' "$CONFIG_FILE"
import sys
try:
    import yaml
    data = yaml.safe_load(open(sys.argv[1], "r", encoding="utf-8")) or {}
    aws = data.get("aws", {})
    print(aws.get("region", "") or "")
except Exception:
    print("")
PY
)"
  fi
  if [ -z "$OPENSEARCH_ENDPOINT" ]; then
    OPENSEARCH_ENDPOINT="$(python3 - <<'PY' "$CONFIG_FILE"
import sys
try:
    import yaml
    data = yaml.safe_load(open(sys.argv[1], "r", encoding="utf-8")) or {}
    aws = data.get("aws", {})
    endpoint = aws.get("opensearch_endpoint") or aws.get("opensearch", {}).get("endpoint")
    print(endpoint or "")
except Exception:
    print("")
PY
)"
  fi
fi

echo "Démarrage de la pile Docker Compose..."
if [ -n "$AWS_ACCESS_KEY_ID" ] || [ -n "$AWS_SECRET_ACCESS_KEY" ] || [ -n "$OPENSEARCH_ENDPOINT" ]; then
  (
    cd "$ROOT_DIR/docker" && sudo env \
      AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
      AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
      AWS_REGION="$AWS_REGION" \
      OPENSEARCH_ENDPOINT="$OPENSEARCH_ENDPOINT" \
      docker compose up -d
  )
else
  (cd "$ROOT_DIR/docker" && sudo docker compose up -d)
fi

echo "Démarrage du service ids2-agent..."
sudo systemctl start ids2-agent.service

echo "Affichage des logs du service ids2-agent (Ctrl+C pour quitter)..."
sudo journalctl -f -u ids2-agent.service
