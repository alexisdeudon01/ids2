#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python - <<'PY'
import sys
from pathlib import Path

root = Path("$ROOT_DIR")
print(f"DB manager ready at {root}")
PY
