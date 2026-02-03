#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'USAGE'
Usage: scripts/gh_codespaces_set_secrets.sh [options]

Create/update Codespaces user secrets needed for CI/CD deploy.

Options:
  --pi-ip IP            Pi Tailscale IP (e.g., 100.x.x.x)
  --pi-user USER        Pi SSH user (e.g., pi)
  --ts-oauth-id ID      Tailscale OAuth client ID
  --ts-oauth-secret KEY Tailscale OAuth client secret
  --ts-tailnet NAME     Tailscale tailnet (e.g., example.com or name)
  --ts-api-key KEY      Tailscale API key (tskey-...)
  --aws-access-key ID   AWS access key id
  --aws-secret-key KEY  AWS secret access key
  --aws-region REGION   AWS region (e.g., eu-west-1)
  --aws-session-token   AWS session token (optional)
  --ssh-key PATH        SSH private key path (default: ~/.ssh/pi_github_actions)
  --repo OWNER/REPO     Set repo-level Codespaces secrets (default: user)
  --skip-ssh-copy       Do not install public key on the Pi
  -h, --help            Show this help

Notes:
  - If GH_TOKEN is missing but GITAPI is set, GITAPI is used.
  - Requires GitHub CLI: https://cli.github.com/
USAGE
}

PI_IP="${PI_IP:-}"
PI_USER="${PI_USER:-}"
TS_OAUTH_CLIENT_ID="${TS_OAUTH_CLIENT_ID:-}"
TS_OAUTH_CLIENT_SECRET="${TS_OAUTH_CLIENT_SECRET:-}"
TAILSCALE_TAILNET="${TAILSCALE_TAILNET:-}"
TAILSCALE_API_KEY="${TAILSCALE_API_KEY:-}"
AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}"
AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}"
AWS_REGION="${AWS_REGION:-}"
AWS_SESSION_TOKEN="${AWS_SESSION_TOKEN:-}"
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/pi_github_actions}"
SKIP_SSH_COPY="0"
REPO=""
SCOPE="user"

while [[ $# -gt 0 ]]; do
  case "$1" in
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
    --ts-tailnet)
      TAILSCALE_TAILNET="$2"
      shift 2
      ;;
    --ts-api-key)
      TAILSCALE_API_KEY="$2"
      shift 2
      ;;
    --aws-access-key)
      AWS_ACCESS_KEY_ID="$2"
      shift 2
      ;;
    --aws-secret-key)
      AWS_SECRET_ACCESS_KEY="$2"
      shift 2
      ;;
    --aws-region)
      AWS_REGION="$2"
      shift 2
      ;;
    --aws-session-token)
      AWS_SESSION_TOKEN="$2"
      shift 2
      ;;
    --ssh-key)
      SSH_KEY_PATH="$2"
      shift 2
      ;;
    --repo)
      REPO="$2"
      SCOPE="repo"
      shift 2
      ;;
    --skip-ssh-copy)
      SKIP_SSH_COPY="1"
      shift 1
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
if [[ -z "$TAILSCALE_TAILNET" ]]; then
  read -rp "Tailscale tailnet: " TAILSCALE_TAILNET
fi
if [[ -z "$TAILSCALE_API_KEY" ]]; then
  read -rsp "Tailscale API key (tskey-...): " TAILSCALE_API_KEY
  echo
fi
if [[ -z "$AWS_ACCESS_KEY_ID" ]]; then
  read -rp "AWS access key id: " AWS_ACCESS_KEY_ID
fi
if [[ -z "$AWS_SECRET_ACCESS_KEY" ]]; then
  read -rsp "AWS secret access key: " AWS_SECRET_ACCESS_KEY
  echo
fi
if [[ -z "$AWS_REGION" ]]; then
  default_region=""
  if [[ -f "$ROOT_DIR/config.yaml" ]]; then
    default_region="$(grep -E '^[[:space:]]*region:' "$ROOT_DIR/config.yaml" | head -1 | sed -E 's/^[[:space:]]*region:[[:space:]]*\"?([^\"[:space:]]+)\"?.*/\\1/')"
  fi
  prompt="AWS region"
  if [[ -n "$default_region" ]]; then
    prompt="${prompt} [${default_region}]"
  fi
  read -rp "${prompt}: " AWS_REGION
  AWS_REGION="${AWS_REGION:-$default_region}"
  AWS_REGION="${AWS_REGION:-us-east-1}"
fi
if [[ -z "$AWS_SESSION_TOKEN" ]]; then
  read -rp "AWS session token (optional): " AWS_SESSION_TOKEN
fi

if [[ -z "$PI_IP" || -z "$PI_USER" ]]; then
  echo "PI_IP and PI_USER are required." >&2
  exit 1
fi
if [[ -z "$TS_OAUTH_CLIENT_ID" || -z "$TS_OAUTH_CLIENT_SECRET" || -z "$TAILSCALE_TAILNET" || -z "$TAILSCALE_API_KEY" ]]; then
  echo "Tailscale OAuth client, tailnet, and API key are required." >&2
  exit 1
fi
if [[ -z "$AWS_ACCESS_KEY_ID" || -z "$AWS_SECRET_ACCESS_KEY" || -z "$AWS_REGION" ]]; then
  echo "AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_REGION are required." >&2
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
    ssh-copy-id -i "${SSH_KEY_PATH}.pub" "${PI_USER}@${PI_IP}"
  else
    cat "${SSH_KEY_PATH}.pub" | ssh "${PI_USER}@${PI_IP}" \
      'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
  fi
fi

if [[ "$SCOPE" == "repo" ]]; then
  if [[ -z "$REPO" ]]; then
    REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
  fi
  SECRET_ARGS=(--app codespaces --repo "$REPO")
else
  SECRET_ARGS=(--app codespaces --user)
fi

printf '%s' "$PI_IP" | gh secret set PI_IP "${SECRET_ARGS[@]}"
printf '%s' "$PI_USER" | gh secret set PI_USER "${SECRET_ARGS[@]}"
printf '%s' "$TS_OAUTH_CLIENT_ID" | gh secret set TS_OAUTH_CLIENT_ID "${SECRET_ARGS[@]}"
printf '%s' "$TS_OAUTH_CLIENT_SECRET" | gh secret set TS_OAUTH_CLIENT_SECRET "${SECRET_ARGS[@]}"
printf '%s' "$TAILSCALE_TAILNET" | gh secret set TAILSCALE_TAILNET "${SECRET_ARGS[@]}"
printf '%s' "$TAILSCALE_API_KEY" | gh secret set TAILSCALE_API_KEY "${SECRET_ARGS[@]}"
printf '%s' "$AWS_ACCESS_KEY_ID" | gh secret set AWS_ACCESS_KEY_ID "${SECRET_ARGS[@]}"
printf '%s' "$AWS_SECRET_ACCESS_KEY" | gh secret set AWS_SECRET_ACCESS_KEY "${SECRET_ARGS[@]}"
printf '%s' "$AWS_REGION" | gh secret set AWS_REGION "${SECRET_ARGS[@]}"
if [[ -n "$AWS_SESSION_TOKEN" ]]; then
  printf '%s' "$AWS_SESSION_TOKEN" | gh secret set AWS_SESSION_TOKEN "${SECRET_ARGS[@]}"
fi
gh secret set PI "${SECRET_ARGS[@]}" < "$SSH_KEY_PATH"

echo "Codespaces secrets set: PI_IP, PI_USER, TS_OAUTH_CLIENT_ID, TS_OAUTH_CLIENT_SECRET, TAILSCALE_TAILNET, TAILSCALE_API_KEY, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, AWS_SESSION_TOKEN, PI"
