#!/usr/bin/env bash
set -euo pipefail

# Verify we're on a Debian/Ubuntu system
if [ ! -d /etc/apt ]; then
  echo "❌ /etc/apt directory not found. This script requires Debian/Ubuntu system."
  exit 1
fi

# Check if directories or files exist
if [ ! -d /etc/apt/sources.list.d ] && [ ! -f /etc/apt/sources.list ]; then
  echo "❌ Aucune source APT détectée."
  exit 1
fi

# Look for .list OR .sources files, or a non-empty sources.list
# Use find instead of ls to avoid errors when no files match
if [ -d /etc/apt/sources.list.d ]; then
  if ! find /etc/apt/sources.list.d -maxdepth 1 -name "*.list" -o -name "*.sources" 2>/dev/null | grep -q .; then
    if [ ! -s /etc/apt/sources.list ]; then
      echo "❌ Aucune source APT active. Vérifiez /etc/apt/sources.list(.d)."
      exit 1
    fi
  fi
elif [ ! -s /etc/apt/sources.list ]; then
  echo "❌ Aucune source APT active."
  exit 1
fi

echo "✅ Sources APT détectées."
