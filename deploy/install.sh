#!/bin/bash

# Script d'installation complet pour le pipeline IDS2 SOC sur Raspberry Pi.
# Ce script installe les dépendances système, Docker, Python, et configure les services.

# Vérifier si le script est exécuté en tant que root
if [ "$EUID" -ne 0 ]; then
  echo "Veuillez exécuter ce script avec sudo."
  exit 1
fi

echo "Mise à jour du système..."
apt update && apt upgrade -y

echo "Installation des dépendances système..."
apt install -y python3-pip python3-venv git curl gnupg2 apt-transport-https ca-certificates software-properties-common

echo "Installation de Docker..."
# Ajouter la clé GPG officielle de Docker
install -m 0555 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Ajouter le dépôt Docker à APT sources
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Ajouter l'utilisateur 'pi' au groupe docker
usermod -aG docker pi

echo "Installation des dépendances Python..."
# Naviguer vers le répertoire python_env et installer les dépendances
(cd python_env && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt)

echo "Rendre les scripts de déploiement exécutables..."
chmod +x deploy/*.sh

echo "Configuration de l'interface réseau (eth0 uniquement)..."
# Copier le script network_eth0_only.sh et le rendre exécutable
cp deploy/network_eth0_only.sh /usr/local/bin/network_eth0_only.sh
chmod +x /usr/local/bin/network_eth0_only.sh

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
