#!/usr/bin/env bash
set -euo pipefail

REMOTE_DIR="${REMOTE_DIR:-/opt/ids-dashboard}"
REQ_FILE="${REMOTE_DIR}/webapp/backend/requirements.txt"
VENV_DIR="${REMOTE_DIR}/webapp/backend/venv"

if [ ! -f "$REQ_FILE" ]; then
  echo "requirements.txt introuvable: $REQ_FILE"
  exit 1
fi

# Check python3 availability
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ python3 command not found. Please install Python 3 first."
  exit 1
fi

# Check python3-venv module
if ! python3 -c "import venv" 2>/dev/null; then
  echo "❌ python3-venv module not available. Installing python3-venv..."
  if [ "$EUID" -eq 0 ] || sudo -n true 2>/dev/null; then
    apt-get update && apt-get install -y python3-venv
  else
    echo "❌ Cannot install python3-venv without root privileges."
    exit 1
  fi
fi

# Create venv if not exists
if [ ! -d "$VENV_DIR" ]; then
  echo "📦 Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

# Install dependencies in venv
echo "📥 Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$REQ_FILE"

echo "✅ Backend dependencies installed in venv"

