#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"

command -v python3 >/dev/null || { echo "❌ python3 requis" >&2; exit 1; }

if ! python3 -c "import tkinter" 2>/dev/null; then
  echo "📦 Installation de tkinter..."
  sudo apt-get update && sudo apt-get install -y python3-tk
fi

if [ ! -d "$VENV" ]; then
  echo "🔧 Création venv..."
  python3 -m venv "$VENV"
fi

source "$VENV/bin/activate"
pip install -q --upgrade pip
pip install -q -r "$ROOT/requirements-deploy.txt"

exec python3 "$ROOT/orchestrator.py"
