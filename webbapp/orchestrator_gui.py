"""Tkinter GUI orchestrator for AWS + Pi2 deployment.

This is a compatibility wrapper. The actual implementation is in ids.deploy package.
"""

from ids.deploy.gui import main, OrchestratorGUI

__all__ = ["OrchestratorGUI", "main"]

if __name__ == "__main__":
    main()
