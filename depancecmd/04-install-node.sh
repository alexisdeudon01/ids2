#!/usr/bin/env bash
set -euo pipefail

# Check for root/sudo privileges
if [ "$EUID" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo "❌ This script requires root privileges. Please run with sudo or as root."
    exit 1
fi

# Verify apt-get is available
if ! command -v apt-get >/dev/null 2>&1; then
    echo "❌ apt-get not found. This script requires Debian/Ubuntu system."
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive

# Verify apt-get is available
if ! command -v apt-get >/dev/null 2>&1; then
    echo "❌ apt-get not found. This script requires Debian/Ubuntu system."
    exit 1
fi

# Check if packages are already installed
if command -v nodejs >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    echo "✅ nodejs and npm already installed"
    nodejs --version
    npm --version
    exit 0
fi

# Check network connectivity
if ! ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1 && ! ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
    echo "⚠️  Warning: Network connectivity check failed. Installation may fail."
fi

# Update package lists before installing
apt-get update

# Install with retry on network failures
max_retries=3
retry_count=0
while [ $retry_count -lt $max_retries ]; do
    if apt-get install -y nodejs npm; then
        break
    else
        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $max_retries ]; then
            echo "⚠️  Installation failed, retrying ($retry_count/$max_retries)..."
            sleep 2
        else
            echo "❌ Failed to install nodejs/npm after $max_retries attempts"
            exit 1
        fi
    fi
done

# Verify installation
if ! command -v nodejs >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo "❌ nodejs/npm installation verification failed"
    exit 1
fi
