#!/bin/bash

# Script d'installation complet pour le pipeline IDS2 SOC sur Raspberry Pi.
# Ce script installe les dépendances système, Docker, Python, et configure les services.

# Vérifier si le script est exécuté en tant que root
if [ "$EUID" -ne 0 ]; then
  echo "Veuillez exécuter ce script avec sudo."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
OWNER_USER="${SUDO_USER:-pi}"

export DEBIAN_FRONTEND=noninteractive
export DEBCONF_NONINTERACTIVE_SEEN=true
export APT_LISTCHANGES_FRONTEND=none

echo "Mise à jour du système..."
apt-get update && apt-get upgrade -y

echo "Installation des dépendances système..."
apt-get install -y python3-venv python3-pip curl gnupg apt-transport-https ca-certificates suricata

echo "Installation de Docker..."
# Supprimer les paquets Docker potentiellement conflictuels
apt-get remove -y docker docker.io docker-doc docker-compose podman-docker containerd runc || true

# Ajouter la clé GPG officielle de Docker
install -m 0555 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --batch --yes --no-tty --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Ajouter le dépôt Docker à APT sources
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "Configuration DNS du daemon Docker (pour éviter les erreurs DNS en conteneur)..."
mkdir -p /etc/docker
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/etc/docker/daemon.json")
data = {}
if path.exists():
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        data = {}
if not isinstance(data, dict):
    data = {}

data.setdefault("dns", ["1.1.1.1", "8.8.8.8"])
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {path}")
PY
systemctl restart docker || true

# Ajouter l'utilisateur au groupe docker
usermod -aG docker "$OWNER_USER"

echo "Installation des dépendances Python (venv)..."
if [ ! -d "$ROOT_DIR/.venv" ]; then
  python3 -m venv "$ROOT_DIR/.venv"
fi
"$ROOT_DIR/.venv/bin/pip" install --upgrade pip
if [ -f "$ROOT_DIR/requirements.txt" ]; then
  "$ROOT_DIR/.venv/bin/pip" install -r "$ROOT_DIR/requirements.txt"
else
  echo "Warning: requirements.txt not found"
fi
chown -R "$OWNER_USER":"$OWNER_USER" "$ROOT_DIR/.venv"

echo "Rendre les scripts de déploiement exécutables..."
find "$ROOT_DIR/deploy" -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true

echo "Configuration de Suricata..."
# Créer le répertoire des règles Suricata si non existant
mkdir -p /etc/suricata/rules
# Copier les règles par défaut ou un placeholder
# Pour une vraie installation, il faudrait télécharger les règles ici
touch /etc/suricata/rules/local.rules # Créer un fichier de règles vide pour éviter les erreurs
# Désactiver le service Suricata par défaut s'il est activé par l'installation
systemctl disable suricata || true
systemctl stop suricata || true

echo "Configuration de l'interface réseau (eth0 uniquement)..."
# Copier le script network_eth0_only.sh et le rendre exécutable
if [ -f "$ROOT_DIR/deploy/network_eth0_only.sh" ]; then
  cp "$ROOT_DIR/deploy/network_eth0_only.sh" /usr/local/bin/network_eth0_only.sh
  chmod +x /usr/local/bin/network_eth0_only.sh
else
  echo "Warning: network_eth0_only.sh not found, skipping network configuration"
fi

# Créer un service systemd pour network_eth0_only.sh
cat <<EOF > /etc/systemd/system/network-eth0-only.service
[Unit]
Description=Ensure only eth0 network interface is active
After=network-pre.target
Before=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/network_eth0_only.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable network-eth0-only.service
systemctl start network-eth0-only.service

echo "Création et montage du RAM disk pour les logs Suricata..."
# Chemin du RAM disk et taille (2GB comme spécifié dans le README)
RAMDISK_PATH="/mnt/ram_logs"
RAMDISK_SIZE="2G" # 2 GB

# Créer le répertoire si non existant
mkdir -p $RAMDISK_PATH

# Monter le RAM disk
mount -t tmpfs -o size=$RAMDISK_SIZE tmpfs $RAMDISK_PATH

# Ajouter au fstab pour persistance après redémarrage (optionnel, dépend si les logs doivent survivre un reboot)
# Pour un RAM disk, il est généralement recréé à chaque démarrage.
# Si la persistance est nécessaire, il faudrait une autre stratégie.
# Pour l'instant, nous nous basons sur la recréation au démarrage.
# echo "tmpfs $RAMDISK_PATH tmpfs nodev,nosuid,size=$RAMDISK_SIZE 0 0" >> /etc/fstab

echo "Installation et configuration initiales terminées."
echo "Veuillez redémarrer votre Raspberry Pi pour que tous les changements prennent effet."
echo "Après le redémarrage, vous pouvez démarrer l'agent avec : sudo deploy/start_agent.sh"
