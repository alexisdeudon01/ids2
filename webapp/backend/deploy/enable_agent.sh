#!/bin/bash

# Script pour installer et activer le service systemd de l'agent IDS2 SOC.

AGENT_SERVICE_FILE="ids2-agent.service"
SURICATA_SERVICE_FILE="suricata.service"
AGENT_SERVICE_PATH="/etc/systemd/system/$AGENT_SERVICE_FILE"
SURICATA_SERVICE_PATH="/etc/systemd/system/$SURICATA_SERVICE_FILE"
CURRENT_DIR="$(dirname "$(readlink -f "$0")")"

echo "Copie du fichier de service $AGENT_SERVICE_FILE vers $AGENT_SERVICE_PATH..."
sudo cp "$CURRENT_DIR/$AGENT_SERVICE_FILE" "$AGENT_SERVICE_PATH"

echo "Copie du fichier de service $SURICATA_SERVICE_FILE vers $SURICATA_SERVICE_PATH..."
sudo cp "$CURRENT_DIR/$SURICATA_SERVICE_FILE" "$SURICATA_SERVICE_PATH"

echo "Rechargement de la configuration systemd..."
sudo systemctl daemon-reload

echo "Activation du service ids2-agent..."
sudo systemctl enable ids2-agent.service

echo "Activation du service suricata..."
sudo systemctl enable suricata.service

echo "Services activés. Ils démarreront automatiquement au prochain redémarrage."
echo "Pour démarrer les services maintenant, exécutez : sudo deploy/start_agent.sh"
