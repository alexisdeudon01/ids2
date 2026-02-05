#!/bin/bash
set -e

MIRROR_INTERFACE="${MIRROR_INTERFACE:-eth0}"

echo "📦 Installation des dépendances..."
sudo apt update && sudo apt install -y suricata python3-pip awscli ufw curl
pip3 install boto3 elasticsearch requests --break-system-packages

echo "🛡️ Configuration réseau & Furtivité..."
sudo ip link set "$MIRROR_INTERFACE" promisc on
sudo ufw --force reset
sudo ufw allow 22/tcp
sudo ufw --force enable

echo "📝 Injection des règles..."
echo 'alert icmp any any -> any any (msg:"[IDS] ICMP DETECTE"; sid:1000001; rev:1;)' | sudo tee /etc/suricata/rules/local.rules
sudo chmod 644 /var/log/suricata/eve.json

# Désactivation du payload dans la conf Suricata
sudo sed -i 's/payload: yes/payload: no/g' /etc/suricata/suricata.yaml

sudo systemctl enable --now suricata
echo "✅ Sonde prête."
