#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'USAGE'
Usage: scripts/gh_actions_bootstrap.sh [options]

One-shot setup:
  1) Generate SSH key
  2) (Optional) Install public key on the Pi
  3) Create Codespaces secrets (repo-level)
  4) Sync to GitHub Actions secrets
  5) Trigger workflow

Options:
  --repo OWNER/REPO     Target repository (default: current repo)
  --pi-ip IP            Pi Tailscale IP (e.g., 100.x.x.x)
  --pi-user USER        Pi SSH user (e.g., pi)
  --ts-oauth-id ID      Tailscale OAuth client ID
  --ts-oauth-secret KEY Tailscale OAuth client secret
  --ts-oauth-tags TAGS  Tailscale tags (e.g., "tag:ci")
  --ssh-key PATH        SSH private key path (default: ~/.ssh/pi_github_actions)
  --skip-ssh-copy       Do not install public key on the Pi
  --no-run              Do not trigger workflow
  --workflow NAME       Workflow file or name (default: ci-cd.yml)
  --ref REF             Git ref (default: main)
  -h, --help            Show this help
USAGE
}

REPO=""
PI_IP="${PI_IP:-}"
PI_USER="${PI_USER:-}"
TS_OAUTH_CLIENT_ID="${TS_OAUTH_CLIENT_ID:-}"
TS_OAUTH_CLIENT_SECRET="${TS_OAUTH_CLIENT_SECRET:-}"
TS_OAUTH_TAGS="${TS_OAUTH_TAGS:-}"
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/pi_github_actions}"
SKIP_SSH_COPY="0"
RUN_WORKFLOW="1"
WORKFLOW="ci-cd.yml"
REF="main"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO="$2"
      shift 2
      ;;
    --pi-ip)
      PI_IP="$2"
      shift 2
      ;;
    --pi-user)
      PI_USER="$2"
      shift 2
      ;;
    --ts-oauth-id)
      TS_OAUTH_CLIENT_ID="$2"
      shift 2
      ;;
    --ts-oauth-secret)
      TS_OAUTH_CLIENT_SECRET="$2"
      shift 2
      ;;
    --ts-oauth-tags)
      TS_OAUTH_TAGS="$2"
      shift 2
      ;;
    --ssh-key)
      SSH_KEY_PATH="$2"
      shift 2
      ;;
    --skip-ssh-copy)
      SKIP_SSH_COPY="1"
      shift 1
      ;;
    --no-run)
      RUN_WORKFLOW="0"
      shift 1
      ;;
    --workflow)
      WORKFLOW="$2"
      shift 2
      ;;
    --ref)
      REF="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "${EUID:-0}" -eq 0 ]]; then
  echo "Do not run this script with sudo. Run as your normal user." >&2
  exit 1
fi

if [[ -z "${GH_TOKEN:-}" && -n "${GITAPI:-}" ]]; then
  export GH_TOKEN="${GITAPI}"
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required. Install from https://cli.github.com/" >&2
  exit 1
fi

if ! gh auth status -h github.com >/dev/null 2>&1; then
  if [[ -z "${GH_TOKEN:-}" ]]; then
    echo "GitHub CLI not authenticated. Run: gh auth login" >&2
    exit 1
  fi
fi

if [[ -z "$PI_IP" ]]; then
  read -rp "Pi Tailscale IP: " PI_IP
fi
if [[ -z "$PI_USER" ]]; then
  read -rp "Pi SSH user: " PI_USER
fi
if [[ -z "$TS_OAUTH_CLIENT_ID" ]]; then
  read -rp "Tailscale OAuth client ID: " TS_OAUTH_CLIENT_ID
fi
if [[ -z "$TS_OAUTH_CLIENT_SECRET" ]]; then
  read -rsp "Tailscale OAuth client secret: " TS_OAUTH_CLIENT_SECRET
  echo
fi
if [[ -z "$TS_OAUTH_TAGS" ]]; then
  read -rp "Tailscale tags (e.g., tag:ci): " TS_OAUTH_TAGS
fi

if [[ -z "$PI_IP" || -z "$PI_USER" || -z "$TS_OAUTH_CLIENT_ID" || -z "$TS_OAUTH_CLIENT_SECRET" || -z "$TS_OAUTH_TAGS" ]]; then
  echo "PI_IP, PI_USER, TS_OAUTH_CLIENT_ID, TS_OAUTH_CLIENT_SECRET, and TS_OAUTH_TAGS are required." >&2
  exit 1
fi

if [[ "$PI_IP" == http://* || "$PI_IP" == https://* ]]; then
  PI_IP="${PI_IP#http://}"
  PI_IP="${PI_IP#https://}"
  PI_IP="${PI_IP%%/*}"
fi

if [[ ! -f "$SSH_KEY_PATH" ]]; then
  mkdir -p "$(dirname "$SSH_KEY_PATH")"
  ssh-keygen -t rsa -b 4096 -m PEM -N "" -f "$SSH_KEY_PATH" -C "github-actions"
fi

if [[ "$SKIP_SSH_COPY" != "1" ]]; then
  if command -v ssh-copy-id >/dev/null 2>&1; then
    if ! ssh-copy-id -i "${SSH_KEY_PATH}.pub" "${PI_USER}@${PI_IP}"; then
      echo "WARN: Failed to install SSH key on the Pi. Install it manually." >&2
    fi
  else
    if ! cat "${SSH_KEY_PATH}.pub" | ssh "${PI_USER}@${PI_IP}" \
      'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'; then
      echo "WARN: Failed to install SSH key on the Pi. Install it manually." >&2
    fi
  fi
fi

if [[ -z "$REPO" ]]; then
  REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
fi

SECRET_ARGS=(--app codespaces --repo "$REPO")
printf '%s' "$PI_IP" | gh secret set PI_IP "${SECRET_ARGS[@]}"
printf '%s' "$PI_USER" | gh secret set PI_USER "${SECRET_ARGS[@]}"
printf '%s' "$TS_OAUTH_CLIENT_ID" | gh secret set TS_OAUTH_CLIENT_ID "${SECRET_ARGS[@]}"
printf '%s' "$TS_OAUTH_CLIENT_SECRET" | gh secret set TS_OAUTH_CLIENT_SECRET "${SECRET_ARGS[@]}"
printf '%s' "$TS_OAUTH_TAGS" | gh secret set TS_OAUTH_TAGS "${SECRET_ARGS[@]}"
gh secret set PI "${SECRET_ARGS[@]}" < "$SSH_KEY_PATH"

echo "Codespaces secrets set: PI_IP, PI_USER, TS_OAUTH_CLIENT_ID, TS_OAUTH_CLIENT_SECRET, TS_OAUTH_TAGS, PI"

export PI_IP PI_USER TS_OAUTH_CLIENT_ID TS_OAUTH_CLIENT_SECRET TS_OAUTH_TAGS
export PI="$(cat "$SSH_KEY_PATH")"
"$ROOT_DIR/scripts/gh_actions_sync_secrets.sh" --repo "$REPO"

if [[ "$RUN_WORKFLOW" == "1" ]]; then
  "$ROOT_DIR/scripts/gh_actions_run.sh" --repo "$REPO" --workflow "$WORKFLOW" --ref "$REF"
else
  echo "Workflow not triggered (use without --no-run to trigger)."
fi