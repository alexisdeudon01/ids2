"""
IDS (Intrusion Detection System) - Système de détection d'intrusions avancé.

Package racine du système IDS avec architecture SOLID et injection de dépendances.
"""

from .app.container import ConteneurDI
from .domain import AlerteIDS, SeveriteAlerte, TypeAlerte

__version__ = "2.0.0"
__author__ = "SIXT R&D"
__license__ = "MIT"
__all__ = [
    "AlerteIDS",
    "ConteneurDI",
    "SeveriteAlerte",
    "TypeAlerte",
]
