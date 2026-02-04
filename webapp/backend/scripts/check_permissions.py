#!/usr/bin/env python3
"""
Convenience wrapper to run the IDS Dashboard permissions pre-flight check.

Run from the repository root:

  python3 webapp/backend/scripts/check_permissions.py --show-commands

Or as a module (inside the backend venv):

  python -m ids.dashboard.permissions_check --show-commands
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend/src to path (same pattern as other scripts in this repo)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ids.dashboard.permissions_check import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())

