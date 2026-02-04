#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
INSTALL_USER="${INSTALL_USER:-${SUDO_USER:-$USER}}"

echo "🐳 Docker setup..."

ensure_user_in_docker_group() {
  local user="$1"
  if [ -z "$user" ]; then
    return 0
  fi
  if ! id -u "$user" >/dev/null 2>&1; then
    echo "⚠️  User '$user' not found; skipping docker group setup."
    return 0
  fi
  groupadd -f docker >/dev/null 2>&1 || true
  echo "👤 Adding $user to the docker group..."
  usermod -aG docker "$user" || true
}

enable_docker_service() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl enable --now docker >/dev/null 2>&1 || true
  fi
}

install_docker_apt() {
  echo "📦 Installing Docker Engine via apt (non-interactive)..."
  apt-get update
  apt-get install -y ca-certificates curl gnupg

  install -m 0755 -d /etc/apt/keyrings

  . /etc/os-release || true
  local repo_os="debian"
  if [ "${ID:-}" = "raspbian" ]; then
    repo_os="raspbian"
  fi

  curl -fsSL "https://download.docker.com/linux/${repo_os}/gpg" \
    | gpg --batch --yes --no-tty --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg

  local arch codename
  arch="$(dpkg --print-architecture)"
  codename="${VERSION_CODENAME:-}"
  if [ -z "$codename" ] && command -v lsb_release >/dev/null 2>&1; then
    codename="$(lsb_release -cs 2>/dev/null || true)"
  fi
  if [ -z "$codename" ]; then
    # Sensible fallback for old / minimal images
    codename="bookworm"
  fi

  echo "deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${repo_os} ${codename} stable" \
    > /etc/apt/sources.list.d/docker.list

  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

if command -v docker >/dev/null 2>&1; then
  echo "✅ Docker already installed: $(docker --version 2>/dev/null || echo 'unknown version')"
  enable_docker_service
  ensure_user_in_docker_group "$INSTALL_USER"
  if ! docker compose version >/dev/null 2>&1; then
    echo "🧩 docker compose plugin missing; attempting to install..."
    apt-get update
    apt-get install -y docker-compose-plugin || true
  fi
  exit 0
fi

install_docker_apt
enable_docker_service
ensure_user_in_docker_group "$INSTALL_USER"

echo "✅ Docker installation complete."
