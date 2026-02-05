"""
Compatibility layer for database storage modules.

Storage implementations now live under webapp/db/storage.
"""

from __future__ import annotations

import sys
from pathlib import Path

DB_ROOT = Path(__file__).resolve().parents[4] / "db"
if DB_ROOT.exists() and str(DB_ROOT) not in sys.path:
    sys.path.insert(0, str(DB_ROOT))

try:
    from storage import crud, database, models, schemas  # type: ignore # noqa: E402
    from storage.crud import *  # type: ignore # noqa: F403,E402
    from storage.database import *  # type: ignore # noqa: F403,E402
    from storage.models import *  # type: ignore # noqa: F403,E402
    from storage.schemas import *  # type: ignore # noqa: F403,E402
except ImportError:
    # Fallback if storage module not available
    import warnings
    warnings.warn("Storage module not available. Database features disabled.", ImportWarning)
    
    class MockModule:
        def __getattr__(self, name):
            raise ImportError(f"Storage module not available: {name}")
    
    crud = database = models = schemas = MockModule()

__all__ = [
    "crud",
    "database",
    "models",
    "schemas",
]
