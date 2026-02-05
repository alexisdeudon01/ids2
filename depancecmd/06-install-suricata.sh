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

# Verify apt-get is available
if ! command -v apt-get >/dev/null 2>&1; then
    echo "❌ apt-get not found. This script requires Debian/Ubuntu system."
    exit 1
fi

# Check for apt lock to avoid race conditions
while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do
    echo "⏳ Waiting for apt lock to be released..."
    sleep 2
done

# Update package lists before installing
apt-get update

# Check network connectivity before installing
if ! ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1 && ! ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
    echo "⚠️  Warning: Network connectivity check failed. Installation may fail."
fi

apt-get install -y suricata suricata-update

# Verify installation
if ! command -v suricata >/dev/null 2>&1; then
    echo "❌ suricata installation verification failed"
    exit 1
fi

if command -v suricata-update >/dev/null 2>&1; then
    # Check network connectivity before updating rules
    if ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1 || ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
        suricata-update || echo "⚠️  Warning: suricata-update failed, but suricata is installed"
    else
        echo "⚠️  Warning: No network connectivity, skipping suricata-update"
    fi
fi
