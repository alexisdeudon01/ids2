#!/usr/bin/env bash
set -euo pipefail

# Check for root/sudo privileges
if [ "$EUID" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo "❌ This script requires root privileges. Please run with sudo or as root."
    exit 1
fi

# Verify GPIO hardware support (basic check for Raspberry Pi)
if [ ! -d "/sys/class/gpio" ] && [ ! -f "/proc/device-tree/model" ]; then
    echo "⚠️  Warning: GPIO hardware not detected. This script is designed for Raspberry Pi."
    echo "   Continuing anyway, but GPIO functionality may not work."
fi

# Set DEBIAN_FRONTEND inline to ensure it persists
DEBIAN_FRONTEND=noninteractive export DEBIAN_FRONTEND

echo "🔨 Building pigpio from source (Trixie compatibility)..."

# 1) Install build tools
apt-get update
apt-get install -y ca-certificates make gcc unzip wget

# 2) Download and extract (use a temp dir to avoid polluting /tmp)
PIGPIO_ARCHIVE_URL="${PIGPIO_ARCHIVE_URL:-http://abyz.me.uk/rpi/pigpio/pigpio.zip}"
# Use process ID and timestamp to ensure unique temp directory
workdir="$(mktemp -d -t pigpio-build-$$-$(date +%s)-XXXXXX)"
cleanup() { rm -rf "$workdir" || true; }
trap cleanup EXIT

archive="${workdir}/pigpio.zip"
echo "⬇️  Downloading pigpio source..."

# Check network connectivity
if ! ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1 && ! ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
    echo "⚠️  Warning: Network connectivity check failed. Download may fail."
fi

# Download with retry mechanism
max_retries=3
retry_count=0
while [ $retry_count -lt $max_retries ]; do
    if wget -qO "$archive" "$PIGPIO_ARCHIVE_URL" --timeout=30 --tries=1; then
        break
    else
        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $max_retries ]; then
            echo "⚠️  Download failed, retrying ($retry_count/$max_retries)..."
            sleep 3
        else
            echo "❌ Failed to download pigpio source after $max_retries attempts"
            exit 1
        fi
    fi
done

if [ ! -f "$archive" ]; then
    echo "❌ Archive file not found after download"
    exit 1
fi

unzip -q "$archive" -d "$workdir"

src_dir="$(find "$workdir" -mindepth 1 -maxdepth 1 -type d -name 'pigpio-*' | head -n 1 || true)"
if [ -z "$src_dir" ] || [ ! -f "$src_dir/Makefile" ]; then
  echo "❌ Could not locate pigpio source directory after extraction."
  echo "📂 Debug: top-level entries in $workdir:"
  ls -la "$workdir" || true
  exit 1
fi

# 3) Compile and install
echo "🔧 Compiling pigpio..."
make -C "$src_dir"
echo "📦 Installing pigpio..."
make -C "$src_dir" install

# 4) Ensure pigpiod is available and start service (best-effort)
if ! command -v pigpiod >/dev/null 2>&1; then
  echo "❌ pigpiod binary not found after install."
  exit 1
fi

if command -v systemctl >/dev/null 2>&1; then
  # Verify systemd directory exists
  if [ ! -d "/etc/systemd/system" ]; then
    echo "⚠️  Warning: /etc/systemd/system directory does not exist. Cannot create service file."
  # If no service exists (common when installing from source), create one.
  elif ! systemctl list-unit-files 2>/dev/null | awk '{print $1}' | grep -qx "pigpiod.service"; then
    pigpiod_path="$(command -v pigpiod)"
    cat > /etc/systemd/system/pigpiod.service <<EOF
[Unit]
Description=Pigpio daemon
After=network.target

[Service]
Type=simple
ExecStart=${pigpiod_path} -g
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload || true
  fi

  systemctl enable pigpiod.service >/dev/null 2>&1 || true
  systemctl restart pigpiod.service >/dev/null 2>&1 || systemctl start pigpiod.service >/dev/null 2>&1 || true
fi

echo "✅ pigpio installed. (pigpiod service enabled if systemd is available)"
