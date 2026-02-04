"""
IDS (Intrusion Detection System) - Système de détection d'intrusions avancé.

Package racine du système IDS avec architecture SOLID et injection de dépendances.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    # Optional imports for type-checkers; avoid hard runtime deps at import time.
    from .app.container import ConteneurDI as ConteneurDI
    from .domain import AlerteIDS as AlerteIDS
    from .domain import SeveriteAlerte as SeveriteAlerte
    from .domain import TypeAlerte as TypeAlerte

__version__ = "2.0.0"
__author__ = "SIXT R&D"
__license__ = "MIT"
__all__ = [
    "AlerteIDS",
    "ConteneurDI",
    "SeveriteAlerte",
    "TypeAlerte",
]


def __getattr__(name: str):  # pragma: no cover
    """
    Lazy attribute access to keep `import ids` lightweight.

    This prevents optional dependencies (e.g., the DI container) from being
    required just to import submodules like `ids.dashboard.*`.
    """

    if name == "ConteneurDI":
        from .app.container import ConteneurDI

        return ConteneurDI
    if name in {"AlerteIDS", "SeveriteAlerte", "TypeAlerte"}:
        from .domain import AlerteIDS, SeveriteAlerte, TypeAlerte

        return {"AlerteIDS": AlerteIDS, "SeveriteAlerte": SeveriteAlerte, "TypeAlerte": TypeAlerte}[name]
    raise AttributeError(name)
