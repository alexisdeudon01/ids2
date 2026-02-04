"""
IDS (Intrusion Detection System) - Système de détection d'intrusions avancé.

Package racine du système IDS avec architecture SOLID et injection de dépendances.
"""

__version__ = "2.0.0"
__author__ = "SIXT R&D"
__license__ = "MIT"


# Lazy imports to avoid circular dependencies
def __getattr__(name):
    """Lazy loading of module attributes."""
    if name == "AlerteIDS":
        from .domain import AlerteIDS

        return AlerteIDS
    if name == "SeveriteAlerte":
        from .domain import SeveriteAlerte

        return SeveriteAlerte
    if name == "TypeAlerte":
        from .domain import TypeAlerte

        return TypeAlerte
    if name == "ConteneurDI":
        from .app.container import ConteneurDI

        return ConteneurDI
    raise AttributeError(f"module 'ids' has no attribute '{name}'")


from .app.container import ConteneurDI

# Define __all__ with actual imports to satisfy pylint
from .domain import AlerteIDS, SeveriteAlerte, TypeAlerte

__all__ = [
    "AlerteIDS",
    "SeveriteAlerte",
    "TypeAlerte",
    "ConteneurDI",
]
