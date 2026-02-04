#!/usr/bin/env bash
set -euo pipefail

# Check for root/sudo privileges
if [ "$EUID" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo "❌ This script requires root privileges. Please run with sudo or as root."
    exit 1
fi

# Verify DEBIAN_FRONTEND is set correctly
if [ -z "${DEBIAN_FRONTEND:-}" ]; then
    export DEBIAN_FRONTEND=noninteractive
fi

# Check for apt lock to avoid race conditions
while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do
    echo "⏳ Waiting for apt lock to be released..."
    sleep 2
done

apt-get install -y suricata suricata-update

if command -v suricata-update >/dev/null 2>&1; then
  suricata-update || true
fi
