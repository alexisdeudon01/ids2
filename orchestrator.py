#!/usr/bin/env python3
"""IDS Deployment Orchestrator - Standalone GUI."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "webapp" / "backend" / "src"))

from ids.deploy.gui import main

if __name__ == "__main__":
    main()
