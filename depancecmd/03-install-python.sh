#!/usr/bin/env bash
set -euo pipefail

# Check for root/sudo privileges
if [ "$EUID" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo "❌ This script requires root privileges. Please run with sudo or as root."
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive

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
