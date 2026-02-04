#!/bin/bash

# Script pour réinitialiser l'environnement du pipeline IDS2 SOC.
# Arrête les services, supprime les conteneurs Docker, et nettoie les fichiers générés.

echo "Arrêt et désactivation du service systemd de l'agent IDS2 SOC..."
sudo systemctl stop ids2-agent.service
sudo systemctl disable ids2-agent.service
sudo rm -f /etc/systemd/system/ids2-agent.service
sudo systemctl daemon-reload

echo "Arrêt et suppression de la pile Docker Compose..."
# Naviguer vers le répertoire docker pour exécuter docker compose down
(cd docker && docker compose down -v --remove-orphans)

echo "Suppression des fichiers de configuration générés..."
rm -f config.yaml
rm -f vector/vector.toml
rm -f suricata/suricata.yaml

echo "Suppression des répertoires de logs RAM (si existants)..."
# Attention: Assurez-vous que /mnt/ram_logs est bien un ramdisk avant de le supprimer
# Pour un ramdisk, un simple 'rmdir' ou 'umount' est suffisant.
# Si ce n'est pas un ramdisk, cela pourrait supprimer des données importantes.
# Pour l'instant, nous allons juste supprimer le fichier eve.json s'il existe.
sudo rm -f /mnt/ram_logs/eve.json

echo "Nettoyage des répertoires du projet..."
rm -rf src/__pycache__
rm -rf src/ids/**/__pycache__
rm -rf docker/grafana/* # Supprimer le contenu de grafana, pas le répertoire lui-même
rm -rf docker/prometheus.yml # Supprimer le fichier prometheus.yml généré
rm -rf vector/* # Supprimer le contenu de vector, pas le répertoire lui-même
rm -rf suricata/* # Supprimer le contenu de suricata, pas le répertoire lui-même

echo "Réinitialisation terminée. L'environnement est propre."
