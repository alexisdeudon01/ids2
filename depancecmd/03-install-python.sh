#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  python3-dev
