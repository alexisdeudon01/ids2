"""
Gestionnaire de Configuration - Chargement et validation de config.yaml.

Implémente l'interface GestionnaireConfig de manière robuste.
Charge et merge les secrets depuis secret.json.
"""

import json
import logging
from pathlib import Path
from typing import Any

import yaml

from ..domain.exceptions import ErreurConfiguration


class ConfigManager:
    """
    Gère le chargement et l'accès à la configuration YAML.

    Implémente le Protocol GestionnaireConfig.
    """

    def __init__(
        self,
        config_path: str | dict[str, Any] = "config.yaml",
        secret_path: str = "secret.json",
    ):
        """
        Initialise le gestionnaire de configuration.

        Args:
            config_path: Chemin vers le fichier config.yaml ou dict en mémoire
            secret_path: Chemin vers le fichier secret.json

        Raises:
            FileNotFoundError: Si le fichier config n'existe pas
        """
        if isinstance(config_path, dict):
            self.config_path = None
            self._config = config_path
        else:
            self.config_path = Path(config_path)
        self.secret_path = Path(secret_path)
        self.logger = logging.getLogger(__name__)

        if self.config_path is not None:
            if not self.config_path.exists():
                raise FileNotFoundError(f"Fichier de configuration introuvable: {self.config_path}")
            self._config = self._charger_config()
        self._charger_secrets()
        if self.config_path is not None:
            self.logger.info(f"Configuration chargée depuis {self.config_path}")
        else:
            self.logger.info("Configuration chargée depuis un dictionnaire")

    @classmethod
    def from_dict(
        cls,
        config: dict[str, Any],
        secret_path: str = "secret.json",
    ) -> "ConfigManager":
        """Crée un ConfigManager à partir d'un dict en mémoire."""
        return cls(config, secret_path=secret_path)

    def _charger_config(self) -> dict[str, Any]:
        """Charge le fichier YAML."""
        try:
            with open(self.config_path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            self.logger.error(f"Erreur lors du parsing YAML: {e}")
            raise

    def _charger_secrets(self) -> None:
        """
        Charge et merge les secrets depuis secret.json dans la configuration.

        Les secrets sont mergés dans self._config, avec priorité aux secrets
        sur la config de base.
        """
        if not self.secret_path.exists():
            if self._aws_endpoint_configured() and not self._use_instance_profile():
                raise ErreurConfiguration(f"Fichier secret.json introuvable: {self.secret_path}")
            self.logger.warning(
                f"Fichier secret.json introuvable: {self.secret_path}. "
                "Les credentials AWS ne seront pas chargés."
            )
            return

        try:
            with open(self.secret_path, encoding="utf-8") as f:
                secrets = json.load(f)

            self._merge_dicts(self._config, secrets)
            if "aws" in secrets:
                self.logger.info("Secrets AWS chargés depuis secret.json")

            self._valider_credentials_aws()

        except json.JSONDecodeError as e:
            self.logger.error(f"Erreur lors du parsing JSON de secret.json: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement de secret.json: {e}")
            raise

    def _merge_dicts(self, base: dict[str, Any], overrides: dict[str, Any]) -> None:
        """Merge overrides into base recursively."""
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._merge_dicts(base[key], value)
            else:
                base[key] = value

    def _aws_endpoint_configured(self) -> bool:
        aws_config = self._config.get("aws", {})
        endpoint = aws_config.get("opensearch_endpoint")
        if endpoint:
            return True
        opensearch = aws_config.get("opensearch", {})
        return bool(opensearch.get("endpoint"))

    def _use_instance_profile(self) -> bool:
        aws_config = self._config.get("aws", {})
        credentials = aws_config.get("credentials", {})
        return bool(credentials.get("use_instance_profile"))

    def _valider_credentials_aws(self) -> None:
        if not self._aws_endpoint_configured():
            return
        if self._use_instance_profile():
            return
        aws_config = self._config.get("aws", {})
        access_key = aws_config.get("access_key_id")
        secret_key = aws_config.get("secret_access_key")
        if not access_key or not secret_key:
            raise ErreurConfiguration(
                "Endpoint OpenSearch configure mais credentials AWS manquants " "dans secret.json"
            )

    def obtenir(self, clé: str, defaut: Any = None) -> Any:
        """
        Obtient une valeur de configuration.

        Supporte les clés imbriquées avec notée pointée :
        Ex: "suricata.config_path" -> self._config["suricata"]["config_path"]

        Args:
            clé: Clé de configuration (peut contenir des points)
            defaut: Valeur par défaut si la clé n'existe pas

        Returns:
            La valeur de configuration ou la valeur par défaut
        """
        parties = clé.split(".")
        valeur = self._config

        for partie in parties:
            if isinstance(valeur, dict) and partie in valeur:
                valeur = valeur[partie]
            else:
                return defaut

        return valeur

    def get(self, clé: str, defaut: Any = None) -> Any:
        """Alias pour obtenir() pour la rétrocompatibilité."""
        return self.obtenir(clé, defaut)

    def definir(self, clé: str, valeur: Any) -> None:
        """
        Définit une valeur de configuration.

        Warning: Cela modifie la configuration en mémoire uniquement,
        pas le fichier sur disque.

        Args:
            clé: Clé de configuration
            valeur: Valeur à définir
        """
        parties = clé.split(".")
        config = self._config

        for partie in parties[:-1]:
            if partie not in config:
                config[partie] = {}
            config = config[partie]

        config[parties[-1]] = valeur
        self.logger.debug(f"Configuration modifiée: {clé} = {valeur}")

    def recharger(self) -> None:
        """Recharge la configuration depuis le fichier et les secrets."""
        if self.config_path is None:
            self.logger.warning("Recharge ignorée: configuration en mémoire uniquement")
            return
        self._config = self._charger_config()
        self._charger_secrets()
        self.logger.info("Configuration rechargée")

    def get_all(self) -> dict[str, Any]:
        """Retourne la configuration complète."""
        return self._config.copy()

    def __repr__(self) -> str:
        return f"ConfigManager({self.config_path})"


__all__ = ["ConfigManager"]
