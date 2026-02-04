#!/usr/bin/env bash
set -euo pipefail

# Check for root/sudo privileges
if [ "$EUID" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo "❌ This script requires root privileges. Please run with sudo or as root."
    exit 1
fi

# Store original DEBIAN_FRONTEND value if set
ORIGINAL_DEBIAN_FRONTEND="${DEBIAN_FRONTEND:-}"
export DEBIAN_FRONTEND=noninteractive

# Check for apt lock to avoid race conditions
while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do
    echo "⏳ Waiting for apt lock to be released..."
    sleep 2
done

# Update package lists before installing
apt-get update

# Check network connectivity
if ! ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1 && ! ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
    echo "⚠️  Warning: Network connectivity check failed. Installation may fail."
fi

apt-get install -y \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  build-essential \
  jq

# Verify installation
for pkg in ca-certificates curl gnupg lsb-release build-essential jq; do
    if ! dpkg -l | grep -q "^ii  $pkg "; then
        echo "⚠️  Warning: Package $pkg may not have installed correctly"
    fi
done

# Restore original DEBIAN_FRONTEND if it was set
if [ -n "$ORIGINAL_DEBIAN_FRONTEND" ]; then
    export DEBIAN_FRONTEND="$ORIGINAL_DEBIAN_FRONTEND"
fi
