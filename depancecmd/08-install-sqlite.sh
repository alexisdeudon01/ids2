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

$APT_GET_CMD install -y sqlite3

# Verify installation
if ! command -v sqlite3 >/dev/null 2>&1; then
    echo "❌ sqlite3 installation verification failed"
    exit 1
fi
sqlite3 --version
