"""
Exceptions métier du système IDS.

Exceptions spécifiques au domaine métier.
"""


class ErreurIDS(Exception):
    """Classe de base pour les erreurs IDS."""

    pass


class ErreurConfiguration(ErreurIDS):
    """Erreur lors du chargement de la configuration."""

    pass


class ErreurConnexion(ErreurIDS):
    """Erreur de connexion à une ressource externe."""

    pass


class ErreurSuricata(ErreurIDS):
    """Erreur spécifique à Suricata."""

    pass


class ErreurDocker(ErreurIDS):
    """Erreur spécifique à Docker."""

    pass


class ErreurAWS(ErreurIDS):
    """Erreur de connexion AWS."""

    pass


class AlerteSourceIndisponible(ErreurIDS):
    """La source d'alertes n'est pas disponible."""

    pass


class DepassementRessources(ErreurIDS):
    """Dépassement des seuils de ressources système."""

    pass


__all__ = [
    "ErreurIDS",
    "ErreurConfiguration",
    "ErreurConnexion",
    "ErreurSuricata",
    "ErreurDocker",
    "ErreurAWS",
    "AlerteSourceIndisponible",
    "DepassementRessources",
]
