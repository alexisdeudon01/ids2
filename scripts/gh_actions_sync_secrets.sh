#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'USAGE'
Usage: scripts/gh_actions_sync_secrets.sh [--repo OWNER/REPO] [--map PATH]

Sync Codespaces environment secrets to GitHub Actions repository secrets.

Options:
  --repo OWNER/REPO   Target repository (default: current repo)
  --map PATH          Mapping file (default: scripts/actions_secrets.map if present)
  -h, --help          Show this help
USAGE
}

REPO=""
MAP_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO="$2"
      shift 2
      ;;
    --map)
      MAP_FILE="$2"
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

if [[ -z "${GH_TOKEN:-}" && -n "${GITAPI:-}" ]]; then
  export GH_TOKEN="${GITAPI}"
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required. Install from https://cli.github.com/" >&2
  exit 1
fi

if [[ -z "$REPO" ]]; then
  REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
fi

if [[ -z "$MAP_FILE" ]]; then
  if [[ -f "${ROOT_DIR}/scripts/actions_secrets.map" ]]; then
    MAP_FILE="${ROOT_DIR}/scripts/actions_secrets.map"
  fi
fi

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

declare -A SECRET_MAP=()

if [[ -n "$MAP_FILE" ]]; then
  if [[ ! -f "$MAP_FILE" ]]; then
    echo "Mapping file not found: $MAP_FILE" >&2
    exit 1
  fi
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="$(trim "$line")"
    [[ -z "$line" || "${line:0:1}" == "#" ]] && continue
    if [[ "$line" != *"="* ]]; then
      echo "Invalid mapping line (expected target=source): $line" >&2
      exit 1
    fi
    target="$(trim "${line%%=*}")"
    source="$(trim "${line#*=}")"
    if [[ -z "$target" || -z "$source" ]]; then
      echo "Invalid mapping line (empty target or source): $line" >&2
      exit 1
    fi
    SECRET_MAP["$target"]="$source"
  done < "$MAP_FILE"
else
  for name in \
    TAILSCALE_OAUTH_CLIENT_ID \
    TAILSCALE_OAUTH_CLIENT_SECRET \
    TAILSCALE_TAILNET \
    TAILSCALE_API_KEY \
    AWS_ACCESS_KEY_ID \
    AWS_SECRET_ACCESS_KEY \
    AWS_SESSION_TOKEN \
    AWS_REGION \
    RASPBERRY_PI_TAILSCALE_IP \
    RASPBERRY_PI_USER \
    RASPBERRY_PI_SSH_KEY \
    SONAR_TOKEN \
    SLACK_WEBHOOK_URL; do
    SECRET_MAP["$name"]="$name"
  done
fi

if [[ ${#SECRET_MAP[@]} -eq 0 ]]; then
  echo "No secrets configured to sync." >&2
  exit 1
fi

updated=0
missing=()

for target in "${!SECRET_MAP[@]}"; do
  source="${SECRET_MAP[$target]}"
  value="${!source-}"
  if [[ -z "$value" ]]; then
    missing+=("${target} (env:${source})")
    continue
  fi
  printf '%s' "$value" | gh secret set "$target" --repo "$REPO"
  echo "Set secret: ${target} (from ${source})"
  updated=$((updated + 1))
done

if [[ $updated -eq 0 ]]; then
  echo "No secrets were updated. Check your env vars or mapping file." >&2
  exit 1
fi

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "Missing env vars for the following targets:" >&2
  for item in "${missing[@]}"; do
    echo "  - ${item}" >&2
  done
fi
