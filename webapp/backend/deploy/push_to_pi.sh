#!/bin/bash

# Script de déploiement vers Raspberry Pi
# Vérifie la connectivité, build l'image Docker, push vers le Pi et active les services

set -e

# Chemins utiles
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/webapp/backend"

# Configuration par défaut
PI_USER="${PI_USER:-pi}"
PI_HOST="${PI_HOST:-192.168.178.66}"
PI_DIR="${PI_DIR:-/opt/ids2}"
DOCKER_IMAGE="ids2-agent:latest"

echo "=== Déploiement IDS2 vers Raspberry Pi ==="
echo "Pi: ${PI_USER}@${PI_HOST}"
echo "Répertoire: ${PI_DIR}"
echo ""

# Fonction de vérification de connectivité
check_connectivity() {
    echo "Vérification de la connectivité SSH..."
    if ! ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "${PI_USER}@${PI_HOST}" "echo 'SSH OK'" > /dev/null 2>&1; then
        echo "ERREUR: Impossible de se connecter au Pi via SSH"
        echo "Vérifiez que:"
        echo "  - Le Pi est accessible sur ${PI_HOST}"
        echo "  - SSH est activé"
        echo "  - Les clés SSH sont configurées"
        exit 1
    fi
    echo "✓ SSH connecté"
    
    echo "Vérification de Docker sur le Pi..."
    if ! ssh "${PI_USER}@${PI_HOST}" "docker --version" > /dev/null 2>&1; then
        echo "ERREUR: Docker n'est pas installé sur le Pi"
        exit 1
    fi
    echo "✓ Docker disponible"
}

# Fonction de build de l'image Docker
build_image() {
    echo ""
    echo "Build de l'image Docker..."
    docker build -t "${DOCKER_IMAGE}" -f "${BACKEND_DIR}/Dockerfile" "${BACKEND_DIR}"
    echo "✓ Image Docker buildée: ${DOCKER_IMAGE}"
}

# Fonction de sauvegarde et transfert de l'image
push_image() {
    echo ""
    echo "Sauvegarde de l'image Docker..."
    IMAGE_TAR="/tmp/ids2-agent.tar"
    docker save "${DOCKER_IMAGE}" -o "${IMAGE_TAR}"
    echo "✓ Image sauvegardée: ${IMAGE_TAR}"
    
    echo "Transfert de l'image vers le Pi..."
    scp "${IMAGE_TAR}" "${PI_USER}@${PI_HOST}:/tmp/"
    echo "✓ Image transférée"
    
    echo "Chargement de l'image sur le Pi..."
    ssh "${PI_USER}@${PI_HOST}" "docker load -i /tmp/ids2-agent.tar && rm /tmp/ids2-agent.tar"
    echo "✓ Image chargée sur le Pi"
    
    rm -f "${IMAGE_TAR}"
}

# Génère docker/.env à partir de config.yaml et secret.json
generate_env_file() {
    echo ""
    echo "Generation de docker/.env..."

    if ! command -v python3 >/dev/null 2>&1; then
        echo "WARN: python3 introuvable, docker/.env non genere."
        return
    fi

    python3 - <<'PY' "$BACKEND_DIR/config.yaml" "$BACKEND_DIR/secret.json" "$REPO_ROOT/docker/.env"
import json
import os
import sys

config_path, secret_path, env_path = sys.argv[1:4]

def load_yaml(path):
    if not os.path.exists(path):
        return {}
    try:
        import yaml
    except Exception:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

config = load_yaml(config_path)
secret = load_json(secret_path)

aws = config.get("aws", {}) if isinstance(config, dict) else {}
opensearch = aws.get("opensearch", {}) if isinstance(aws, dict) else {}
endpoint = aws.get("opensearch_endpoint") or opensearch.get("endpoint")
region = aws.get("region")

secret_aws = secret.get("aws", {}) if isinstance(secret, dict) else {}

lines = []
if secret_aws.get("access_key_id"):
    lines.append(f"AWS_ACCESS_KEY_ID={secret_aws['access_key_id']}")
if secret_aws.get("secret_access_key"):
    lines.append(f"AWS_SECRET_ACCESS_KEY={secret_aws['secret_access_key']}")
if region:
    lines.append(f"AWS_REGION={region}")
if endpoint:
    lines.append(f"OPENSEARCH_ENDPOINT={endpoint}")

os.makedirs(os.path.dirname(env_path), exist_ok=True)

if lines:
    with open(env_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print(f"docker/.env generated ({len(lines)} vars)")
else:
    if os.path.exists(env_path):
        os.remove(env_path)
        print("docker/.env removed (no variables to write)")
    else:
        print("No variables to write in docker/.env")
PY
}

# Fonction de synchronisation des fichiers
sync_files() {
    echo ""
    echo "Synchronisation des fichiers vers le Pi..."
    
    # Créer le répertoire sur le Pi
    ssh "${PI_USER}@${PI_HOST}" "mkdir -p ${PI_DIR}/{docker,service,webapp/backend,webapp/db/config}"
    
    # Synchroniser les fichiers nécessaires
    rsync -avz --exclude='__pycache__' --exclude='*.pyc' \
        "${BACKEND_DIR}/src/" "${PI_USER}@${PI_HOST}:${PI_DIR}/webapp/backend/src/"
    
    rsync -avz \
        "${BACKEND_DIR}/deploy/" "${PI_USER}@${PI_HOST}:${PI_DIR}/webapp/backend/deploy/"
    
    rsync -avz \
        "${REPO_ROOT}/docker/" "${PI_USER}@${PI_HOST}:${PI_DIR}/docker/"
    
    rsync -avz \
        "${REPO_ROOT}/service/" "${PI_USER}@${PI_HOST}:${PI_DIR}/service/"

    rsync -avz \
        "${REPO_ROOT}/webapp/db/config/" "${PI_USER}@${PI_HOST}:${PI_DIR}/webapp/db/config/"
    
    # Copier les fichiers de configuration
    scp "${BACKEND_DIR}/config.yaml" "${PI_USER}@${PI_HOST}:${PI_DIR}/webapp/backend/"
    if [ -f "${BACKEND_DIR}/secret.json" ]; then
        scp "${BACKEND_DIR}/secret.json" "${PI_USER}@${PI_HOST}:${PI_DIR}/webapp/backend/"
    fi
    scp "${BACKEND_DIR}/secret.json.example" "${PI_USER}@${PI_HOST}:${PI_DIR}/webapp/backend/" 2>/dev/null || true
    scp "${BACKEND_DIR}/requirements.txt" "${PI_USER}@${PI_HOST}:${PI_DIR}/webapp/backend/"
    scp "${BACKEND_DIR}/pyproject.toml" "${PI_USER}@${PI_HOST}:${PI_DIR}/webapp/backend/" 2>/dev/null || true
    
    echo "✓ Fichiers synchronisés"
}

# Fonction d'activation des services
enable_services() {
    echo ""
    echo "Activation des services systemd..."
    
    # Copier les services systemd
    ssh "${PI_USER}@${PI_HOST}" "sudo cp ${PI_DIR}/service/ids2-agent.service /etc/systemd/system/"
    ssh "${PI_USER}@${PI_HOST}" "sudo cp ${PI_DIR}/service/suricata.service /etc/systemd/system/"
    ssh "${PI_USER}@${PI_HOST}" "sudo cp ${PI_DIR}/deploy/network_eth0_only.sh /usr/local/bin/"
    ssh "${PI_USER}@${PI_HOST}" "sudo chmod +x /usr/local/bin/network_eth0_only.sh"
    
    # Recharger systemd
    ssh "${PI_USER}@${PI_HOST}" "sudo systemctl daemon-reload"
    
    # Activer les services
    ssh "${PI_USER}@${PI_HOST}" "sudo systemctl enable ids2-agent.service"
    ssh "${PI_USER}@${PI_HOST}" "sudo systemctl enable suricata.service"
    ssh "${PI_USER}@${PI_HOST}" "sudo systemctl enable network-eth0-only.service || true"
    
    echo "✓ Services activés"
    
    echo ""
    echo "Démarrage de la pile Docker Compose..."
    ssh "${PI_USER}@${PI_HOST}" "cd ${PI_DIR}/docker && docker compose up -d"
    echo "✓ Docker Compose démarré"
}

# Fonction principale
main() {
    check_connectivity
    build_image
    push_image
    generate_env_file
    sync_files
    enable_services
    
    echo ""
    echo "=== Déploiement terminé avec succès ==="
    echo ""
    echo "Pour démarrer les services sur le Pi:"
    echo "  ssh ${PI_USER}@${PI_HOST} 'sudo systemctl start suricata.service'"
    echo "  ssh ${PI_USER}@${PI_HOST} 'sudo systemctl start ids2-agent.service'"
    echo ""
    echo "Pour voir les logs:"
    echo "  ssh ${PI_USER}@${PI_HOST} 'sudo journalctl -f -u ids2-agent.service'"
}

main "$@"
