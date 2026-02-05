#!/usr/bin/env bash
set -euo pipefail

# Check for root/sudo privileges
if [ "$EUID" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo "❌ This script requires root privileges. Please run with sudo or as root."
    exit 1
fi

# Verify apt-get exists
if ! command -v apt-get >/dev/null 2>&1; then
    echo "❌ apt-get not found. This script requires Debian/Ubuntu system."
    exit 1
fi

# Check for apt lock to avoid race conditions
while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do
    echo "⏳ Waiting for apt lock to be released..."
    sleep 2
done

export DEBIAN_FRONTEND=noninteractive

# Check network connectivity before attempting updates
if ! ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1 && ! ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
    echo "⚠️  Warning: Network connectivity check failed. Updates may fail."
fi

# Retry mechanism for network issues
max_retries=3
retry_count=0
while [ $retry_count -lt $max_retries ]; do
    if apt-get update -y && apt-get upgrade -y; then
        echo "✅ System updated successfully"
        exit 0
    else
        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $max_retries ]; then
            echo "⚠️  Update failed, retrying ($retry_count/$max_retries)..."
            sleep 5
        else
            echo "❌ Failed to update system after $max_retries attempts"
            exit 1
        fi
    fi
done
