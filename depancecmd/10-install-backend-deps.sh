#!/usr/bin/env bash
set -euo pipefail

REMOTE_DIR="${REMOTE_DIR:-/opt/ids-dashboard}"
REQ_FILE="${REMOTE_DIR}/webapp/backend/requirements.txt"
VENV_DIR="${REMOTE_DIR}/webapp/backend/venv"

if [ ! -f "$REQ_FILE" ]; then
  echo "requirements.txt introuvable: $REQ_FILE"
  exit 1
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

