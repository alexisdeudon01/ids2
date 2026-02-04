#!/bin/bash
set -e

echo "📦 Installing GPIO libraries for Pi 5..."

sudo apt update
sudo apt install -y gpiod libgpiod-dev python3-libgpiod

# If python3-lgpio available, install it
sudo apt install -y python3-lgpio 2>/dev/null || {
    echo "📥 Installing lgpio via pip..."
    sudo apt install -y python3-pip
    pip install lgpio --break-system-packages
}

echo "✅ Done!"

# Test
echo "🔍 Testing GPIO access..."
gpioinfo | head -20
