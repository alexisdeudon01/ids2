#!/bin/bash

# Script pour arrêter proprement le service systemd de l'agent IDS2 SOC.

echo "Arrêt du service ids2-agent..."
sudo systemctl stop ids2-agent.service

echo "Arrêt du service Suricata..."
sudo systemctl stop suricata.service

echo "Arrêt de la pile Docker Compose..."
# Naviguer vers le répertoire docker et arrêter la pile
(cd docker && sudo docker compose down)

echo "Services arrêtés."
