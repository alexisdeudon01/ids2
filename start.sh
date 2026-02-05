#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "❌ Commande requise manquante: $cmd" >&2
    exit 1
  fi
}

ensure_tk() {
  if python3 - <<'PY'
import importlib.util
raise SystemExit(0 if importlib.util.find_spec('tkinter') else 1)
PY
  then
    return 0
  fi

  if command -v apt-get >/dev/null 2>&1; then
    echo "📦 Installation de tkinter (python3-tk)..."
    sudo apt-get update
    sudo apt-get install -y python3-tk
  else
    echo "⚠️  tkinter introuvable. Installez python3-tk avec votre gestionnaire de paquets." >&2
    exit 1
  fi
}

setup_venv() {
  require_cmd python3
  
  if [ ! -d "$VENV_DIR" ]; then
    echo "🔧 Création de l'environnement virtuel .venv..."
    python3 -m venv "$VENV_DIR"
  fi
  
  source "$VENV_DIR/bin/activate"
  
  echo "📥 Installation des dépendances..."
  pip install -q --upgrade pip
  pip install -q -r "$ROOT_DIR/requirements-deploy.txt"
}

ensure_tk
setup_venv

exec python3 "$ROOT_DIR/orchestrator.py"
