#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

echo "🔨 Building pigpio from source (Trixie compatibility)..."

# 1) Install build tools
apt-get update
apt-get install -y ca-certificates make gcc unzip wget

# 2) Download and extract (use a temp dir to avoid polluting /tmp)
PIGPIO_ARCHIVE_URL="${PIGPIO_ARCHIVE_URL:-https://github.com/joan2937/pigpio/archive/refs/heads/master.zip}"
workdir="$(mktemp -d -t pigpio-build-XXXXXX)"
cleanup() { rm -rf "$workdir" || true; }
trap cleanup EXIT

archive="${workdir}/pigpio.zip"
echo "⬇️  Downloading pigpio source..."
wget -qO "$archive" "$PIGPIO_ARCHIVE_URL"
unzip -q "$archive" -d "$workdir"

src_dir="$(find "$workdir" -maxdepth 1 -type d -name 'pigpio-*' | head -n 1 || true)"
if [ -z "$src_dir" ] || [ ! -f "$src_dir/Makefile" ]; then
  echo "❌ Could not locate pigpio source directory after extraction."
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
  # If no service exists (common when installing from source), create one.
  if ! systemctl list-unit-files 2>/dev/null | awk '{print $1}' | grep -qx "pigpiod.service"; then
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
