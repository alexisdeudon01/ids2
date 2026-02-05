#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$ROOT_DIR/webbapp"

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

install_python_deps() {
  require_cmd python3
  if ! python3 -m pip --version >/dev/null 2>&1; then
    python3 -m ensurepip --upgrade
  fi

  local pip_args=()
  if python3 -m pip install --help 2>/dev/null | grep -q "break-system-packages"; then
    pip_args+=("--break-system-packages")
  fi

  echo "📥 Installation des prérequis Python..."
  python3 -m pip install -q --upgrade pip
  python3 -m pip install -q "${pip_args[@]}" -r "$APP_DIR/requirements.txt"
}

ensure_tk
install_python_deps

exec python3 "$ROOT_DIR/orchestrator.py"
