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

apt-get install -y \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  build-essential \
  jq

# Restore original DEBIAN_FRONTEND if it was set
if [ -n "$ORIGINAL_DEBIAN_FRONTEND" ]; then
    export DEBIAN_FRONTEND="$ORIGINAL_DEBIAN_FRONTEND"
fi
