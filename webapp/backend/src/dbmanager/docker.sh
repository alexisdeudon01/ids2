#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="ids2-dbmanager:latest"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/install.sh"

docker build -t "${IMAGE_NAME}" "${SCRIPT_DIR}"

echo "Built ${IMAGE_NAME}"
