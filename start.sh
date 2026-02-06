#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v python3 >/dev/null || { echo "❌ python3 requis" >&2; exit 1; }

if ! python3 -c "import tkinter" 2>/dev/null; then
  echo "📦 Installation de tkinter..."
  sudo apt-get update && sudo apt-get install -y python3-tk
fi

REQ="$ROOT/requirements.txt"

if [ -f "$REQ" ]; then
  if ! python3 -c "import fastapi, boto3, requests, paramiko" >/dev/null 2>&1; then
    echo "📦 Installation des dépendances Python..."
    python3 -m pip install -q --upgrade pip || true

    set +e
    python3 -m pip install -q -r "$REQ" \
      || python3 -m pip install -q --user -r "$REQ" \
      || python3 -m pip install -q --break-system-packages -r "$REQ" \
      || python3 -m pip install -q --user --break-system-packages -r "$REQ"
    set -e

    if ! python3 -c "import fastapi, boto3, requests, paramiko" >/dev/null 2>&1; then
      cat >&2 <<'EOF'
❌ Dépendances Python manquantes, et pip n'a pas pu installer (souvent PEP668 "externally-managed").

Solutions possibles:
- (Recommandé) Créer un venv: `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
- Ou autoriser pip: `python3 -m pip install --break-system-packages -r requirements.txt`
- Ou installer via apt les paquets python3-* correspondants si disponibles.
EOF
      exit 1
    fi
  fi
else
  echo "⚠️ requirements.txt introuvable: $REQ" >&2
fi

exec python3 "$ROOT/orchestrator.py"
