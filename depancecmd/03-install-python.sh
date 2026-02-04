#!/usr/bin/env bash
set -euo pipefail

# Check for root/sudo privileges
if [ "$EUID" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo "❌ This script requires root privileges. Please run with sudo or as root."
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive

# Verify apt-get is available
if ! command -v apt-get >/dev/null 2>&1; then
    echo "❌ apt-get not found. This script requires Debian/Ubuntu system."
    exit 1
fi

# Check network connectivity
if ! ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1 && ! ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
    echo "⚠️  Warning: Network connectivity check failed. Installation may fail."
fi

# Update package lists before installing
apt-get update

apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  python3-dev

# Verify installation
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ python3 installation failed"
    exit 1
fi
python3 --version
