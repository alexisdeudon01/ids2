#!/usr/bin/env python3
"""IDS Deployment Orchestrator - Standalone GUI."""

import sys
from pathlib import Path

webbapp_path = str(Path(__file__).parent / "webbapp")
if webbapp_path not in sys.path:
    sys.path.insert(0, webbapp_path)

if __name__ == "__main__":
    try:
        from ids.deploy.gui import main
        main()
    except ImportError as e:
        print("Failed to import 'ids.deploy.gui'. Make sure it is installed and available in your PYTHONPATH.")
        print(f"ImportError: {e}")
        sys.exit(1)
