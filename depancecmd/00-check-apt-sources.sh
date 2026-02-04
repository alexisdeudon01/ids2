#!/usr/bin/env bash
set -euo pipefail

# Vérifie rapidement que des sources APT existent avant les scripts d'installation.
# Utile sur des images minimales où /etc/apt/sources.list(.d) peut être vide.

if [ ! -d /etc/apt/sources.list.d ] && [ ! -f /etc/apt/sources.list ]; then
  echo "Aucune source APT détectée."
  exit 1
fi

# Cherche des fichiers .list ou .sources, ou un sources.list non vide.
if ! ls /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources >/dev/null 2>&1; then
  if [ ! -s /etc/apt/sources.list ]; then
    echo "Aucune source APT active. Vérifiez /etc/apt/sources.list(.d)."
    exit 1
  fi
fi

echo "Sources APT détectées."

