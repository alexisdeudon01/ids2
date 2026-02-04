#!/usr/bin/env bash
set -euo pipefail

# Check if directories or files exist
if [ ! -d /etc/apt/sources.list.d ] && [ ! -f /etc/apt/sources.list ]; then
  echo "Aucune source APT détectée."
  exit 1
fi

# Look for .list OR .sources files, or a non-empty sources.list
if ! ls /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources >/dev/null 2>&1; then
  if [ ! -s /etc/apt/sources.list ]; then
    echo "Aucune source APT active. Vérifiez /etc/apt/sources.list(.d)."
    exit 1
  fi
fi

echo "Sources APT détectées."
