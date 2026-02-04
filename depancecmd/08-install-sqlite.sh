#!/usr/bin/env bash
set -euo pipefail

# Check for root/sudo privileges
if [ "$EUID" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo "❌ This script requires root privileges. Please run with sudo or as root."
    exit 1
fi

# Verify apt-get is available (use full path if needed)
APT_GET_CMD="$(command -v apt-get 2>/dev/null || echo '/usr/bin/apt-get')"
if [ ! -x "$APT_GET_CMD" ]; then
    echo "❌ apt-get not found at $APT_GET_CMD. This script requires Debian/Ubuntu system."
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive

# Check for apt lock to avoid race conditions
while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do
    echo "⏳ Waiting for apt lock to be released..."
    sleep 2
done

# Update package lists before installing
$APT_GET_CMD update

# Check network connectivity
if ! ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1 && ! ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
    echo "⚠️  Warning: Network connectivity check failed. Installation may fail."
fi

$APT_GET_CMD install -y sqlite3

# Verify installation
if ! command -v sqlite3 >/dev/null 2>&1; then
    echo "❌ sqlite3 installation verification failed"
    exit 1
fi
sqlite3 --version
