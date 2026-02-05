#!/bin/bash
set -euo pipefail

if [ ! -d ".venv" ]; then
  echo "📦 Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "📥 Installing Python prerequisites (FastAPI, etc.)..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

python3 - <<'PY'
import importlib.util
if importlib.util.find_spec('tkinter') is None:
    print('⚠️  tkinter not found. Install with: sudo apt install -y python3-tk')
else:
    print('✅ tkinter available')
PY

echo "✅ Prerequisites installed."
