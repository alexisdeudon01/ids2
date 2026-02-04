#!/usr/bin/env bash
set -euo pipefail

# Check for root/sudo privileges
if [ "$EUID" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo "❌ This script requires root privileges. Please run with sudo or as root."
    exit 1
fi

# Verify ip command is available
if ! command -v ip >/dev/null 2>&1; then
    echo "❌ ip command not found. Please install iproute2: sudo apt-get install -y iproute2"
    exit 1
fi

MIRROR_INTERFACE="${MIRROR_INTERFACE:-eth0}"

# Validate that MIRROR_INTERFACE exists
if ! ip link show "$MIRROR_INTERFACE" >/dev/null 2>&1; then
    echo "❌ Interface $MIRROR_INTERFACE not found. Available interfaces:"
    ip -o link show | awk -F': ' '{print $2}'
    exit 1
fi

# Warn user about potential network disruption
echo "⚠️  WARNING: This script will disable all network interfaces except ${MIRROR_INTERFACE}."
echo "⚠️  This may cause network disruption. Press Ctrl+C to cancel within 5 seconds..."
sleep 5

echo "Désactivation des interfaces autres que ${MIRROR_INTERFACE}..."
failed_interfaces=()
while IFS= read -r iface; do
  if [ "$iface" != "lo" ] && [ "$iface" != "$MIRROR_INTERFACE" ]; then
    if ! ip link set "$iface" down 2>/dev/null; then
      failed_interfaces+=("$iface")
      echo "⚠️  Warning: Failed to bring down interface $iface"
    fi
  fi
done < <(ip -o link show | awk -F': ' '{print $2}')

if [ ${#failed_interfaces[@]} -gt 0 ]; then
  echo "⚠️  Warning: Some interfaces could not be brought down: ${failed_interfaces[*]}"
fi

echo "Activation du mode promiscuous sur ${MIRROR_INTERFACE}..."
if ! ip link set "$MIRROR_INTERFACE" promisc on 2>/dev/null; then
  echo "❌ Failed to enable promiscuous mode on $MIRROR_INTERFACE"
  exit 1
fi
echo "✅ Promiscuous mode enabled on $MIRROR_INTERFACE"
