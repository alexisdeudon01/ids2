#!/bin/bash
set -e

SERVICE_NAME="redis"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing ${SERVICE_NAME} systemd service..."

# Copy service file
sudo cp "${SCRIPT_DIR}/${SERVICE_NAME}.service" "${SERVICE_FILE}"

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"

echo "${SERVICE_NAME} service installed successfully"
echo "Start with: sudo systemctl start ${SERVICE_NAME}"
echo "Status: sudo systemctl status ${SERVICE_NAME}"