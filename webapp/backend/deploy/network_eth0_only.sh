#!/bin/bash

# Script pour configurer le Raspberry Pi afin d'utiliser uniquement l'interface réseau eth0.
# Désactive les autres interfaces et est sûr pour l'accès SSH.
# Peut être activé au démarrage via systemd.

# Vérifier si le script est exécuté en tant que root
if [ "$EUID" -ne 0 ]; then
  echo "Veuillez exécuter ce script avec sudo."
  exit 1
fi

NETWORK_INTERFACE="eth0"

echo "Désactivation de toutes les interfaces réseau sauf $NETWORK_INTERFACE..."

# Obtenir la liste de toutes les interfaces réseau (sauf loopback)
ALL_INTERFACES=$(ip -o link show | awk -F': ' '{print $2}' | grep -v "lo")

for IFACE in $ALL_INTERFACES; do
  if [ "$IFACE" != "$NETWORK_INTERFACE" ]; then
    echo "Désactivation de l'interface $IFACE..."
    ip link set "$IFACE" down
    # Optionnel: Supprimer la configuration DHCP/statique pour cette interface
    # sudo dhclient -r "$IFACE" # Libérer l'adresse IP
    # Supprimer les entrées de /etc/network/interfaces.d/ ou /etc/netplan/*.yaml si nécessaire
  fi
done

echo "Activation de l'interface $NETWORK_INTERFACE..."
ip link set "$NETWORK_INTERFACE" up

echo "Configuration réseau appliquée : seule l'interface $NETWORK_INTERFACE est active."
echo "Vérifiez la connectivité SSH après l'exécution."

# Pour rendre cette configuration persistante au démarrage, vous pouvez créer un service systemd.
# Exemple de fichier de service (par exemple, /etc/systemd/system/network-eth0-only.service):
# [Unit]
# Description=Ensure only eth0 network interface is active
# After=network-pre.target
# Before=network.target
#
# [Service]
# Type=oneshot
# ExecStart=/home/pi/deploy/network_eth0_only.sh
# RemainAfterExit=yes
#
# [Install]
# WantedBy=multi-user.target
#
# Ensuite, activez-le avec :
# sudo systemctl enable network-eth0-only.service
