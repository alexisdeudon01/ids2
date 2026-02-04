#!/usr/bin/env bash
set -euo pipefail

MIRROR_INTERFACE="${MIRROR_INTERFACE:-eth0}"

echo "Désactivation des interfaces autres que ${MIRROR_INTERFACE}..."
while IFS= read -r iface; do
  if [ "$iface" != "lo" ] && [ "$iface" != "$MIRROR_INTERFACE" ]; then
    ip link set "$iface" down || true
  fi
done < <(ip -o link show | awk -F': ' '{print $2}')

echo "Activation du mode promiscuous sur ${MIRROR_INTERFACE}..."
ip link set "$MIRROR_INTERFACE" promisc on || true
