#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get install -y suricata suricata-update

if command -v suricata-update >/dev/null 2>&1; then
  suricata-update || true
fi
