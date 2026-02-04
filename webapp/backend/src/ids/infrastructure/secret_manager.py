"""
Gestionnaire de secrets avec pattern singleton et base de données.

Ce module fournit une classe singleton SecretManager qui permet de :
- Stocker les secrets dans la base de données SQLite
- Récupérer les secrets depuis la base de données
- Initialiser la base de données si nécessaire
- Fournir une interface unique pour accéder aux secrets dans tout le projet
"""

import logging
import os
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SecretManager:
    """
    Gestionnaire de secrets singleton.
    
    Les secrets sont stockés dans la base de données SQLite et récupérés
    via cette classe. Plus besoin de variables d'environnement ou de fichiers
    secrets.json - tout passe par la base de données.
    """
    
    _instance: Optional['SecretManager'] = None
    _lock: Lock = Lock()
    
    def __new__(cls) -> 'SecretManager':
        """Implémentation du pattern singleton."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """Initialise le gestionnaire de secrets."""
        if self._initialized:
            return
        
        self._initialized = True
        self._session = None
        self._secrets_cache: Dict[str, Optional[str]] = {}
        self._db_initialized = False
        
        # Initialiser la base de données
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialise la base de données si nécessaire."""
        try:
            from ids.storage import database, models
            
            # Créer les tables si elles n'existent pas
            database.init_db()
            self._db_initialized = True
            logger.info("Database initialized for SecretManager")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            self._db_initialized = False
    
    def _get_session(self):
        """Récupère une session de base de données."""
        if not self._db_initialized:
            self._init_database()
        
        try:
            from ids.storage import database, crud, models
            
            # Créer une nouvelle session
            session = database.SessionLocal()
            return session
        except Exception as e:
            logger.error(f"Failed to get database session: {e}")
            return None
    
    def get_secret(self, secret_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Récupère un secret depuis la base de données.
        
        Args:
            secret_name: Nom du secret (ex: 'aws_access_key_id', 'tailscale_api_key')
            default: Valeur par défaut si le secret n'existe pas
            
        Returns:
            La valeur du secret ou default
        """
        # Vérifier le cache d'abord
        if secret_name in self._secrets_cache:
            return self._secrets_cache[secret_name]
        
        session = self._get_session()
        if not session:
            logger.warning(f"Database session not available, using default for {secret_name}")
            return default
        
        try:
            from ids.storage import crud, models
            
            # Récupérer le singleton Secrets
            secrets = crud.get_or_create_singleton(session, models.Secrets)
            
            # Mapper les noms de secrets aux attributs du modèle
            secret_mapping = {
                "aws_access_key_id": secrets.aws_access_key_id,
                "aws_secret_access_key": secrets.aws_secret_access_key,
                "aws_session_token": secrets.aws_session_token,
                "tailscale_api_key": secrets.tailscale_api_key,
                "tailscale_oauth_client_id": secrets.tailscale_oauth_client_id,
                "tailscale_oauth_client_secret": secrets.tailscale_oauth_client_secret,
                "elasticsearch_username": secrets.elasticsearch_username,
                "elasticsearch_password": secrets.elasticsearch_password,
                "pi_ssh_user": secrets.pi_ssh_user,
                "pi_ssh_password": secrets.pi_ssh_password,
                "pi_sudo_password": secrets.pi_sudo_password,
            }
            
            value = secret_mapping.get(secret_name)
            
            # Mettre en cache
            self._secrets_cache[secret_name] = value
            
            if value:
                logger.debug(f"Retrieved secret {secret_name} from database")
                return value
            else:
                logger.debug(f"Secret {secret_name} not found in database, using default")
                return default
                
        except Exception as e:
            logger.error(f"Failed to get secret {secret_name}: {e}")
            return default
        finally:
            session.close()
    
    def set_secret(self, secret_name: str, value: str) -> bool:
        """
        Définit un secret dans la base de données.
        
        Args:
            secret_name: Nom du secret
            value: Valeur du secret
            
        Returns:
            True si la sauvegarde a réussi
        """
        session = self._get_session()
        if not session:
            logger.error("Database session not available")
            return False
        
        try:
            from ids.storage import crud, models
            
            # Récupérer le singleton Secrets
            secrets = crud.get_or_create_singleton(session, models.Secrets)
            
            # Mapper les noms de secrets aux attributs du modèle
            secret_mapping = {
                "aws_access_key_id": "aws_access_key_id",
                "aws_secret_access_key": "aws_secret_access_key",
                "aws_session_token": "aws_session_token",
                "tailscale_api_key": "tailscale_api_key",
                "tailscale_oauth_client_id": "tailscale_oauth_client_id",
                "tailscale_oauth_client_secret": "tailscale_oauth_client_secret",
                "elasticsearch_username": "elasticsearch_username",
                "elasticsearch_password": "elasticsearch_password",
                "pi_ssh_user": "pi_ssh_user",
                "pi_ssh_password": "pi_ssh_password",
                "pi_sudo_password": "pi_sudo_password",
            }
            
            if secret_name not in secret_mapping:
                logger.error(f"Unknown secret name: {secret_name}")
                return False
            
            # Définir l'attribut
            setattr(secrets, secret_mapping[secret_name], value)
            
            # Sauvegarder
            session.commit()
            
            # Mettre à jour le cache
            self._secrets_cache[secret_name] = value
            
            logger.info(f"Secret {secret_name} saved to database")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set secret {secret_name}: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def set_secrets_batch(self, secrets: Dict[str, str]) -> Dict[str, bool]:
        """
        Définit plusieurs secrets en une seule opération.
        
        Args:
            secrets: Dictionnaire de secrets {nom: valeur}
            
        Returns:
            Dictionnaire avec le statut de chaque secret
        """
        results = {}
        for secret_name, value in secrets.items():
            results[secret_name] = self.set_secret(secret_name, value)
        return results
    
    def load_secrets_from_env(self, prefix: str = "IDS_") -> int:
        """
        Charge les secrets depuis les variables d'environnement.
        
        Utile pour l'initialisation depuis un fichier .env ou des variables
        d'environnement système.
        
        Args:
            prefix: Préfixe des variables d'environnement (ex: 'IDS_AWS_ACCESS_KEY_ID')
            
        Returns:
            Nombre de secrets chargés
        """
        env_mapping = {
            f"{prefix}AWS_ACCESS_KEY_ID": "aws_access_key_id",
            f"{prefix}AWS_SECRET_ACCESS_KEY": "aws_secret_access_key",
            f"{prefix}AWS_SESSION_TOKEN": "aws_session_token",
            f"{prefix}TAILSCALE_API_KEY": "tailscale_api_key",
            f"{prefix}TAILSCALE_OAUTH_CLIENT_ID": "tailscale_oauth_client_id",
            f"{prefix}TAILSCALE_OAUTH_CLIENT_SECRET": "tailscale_oauth_client_secret",
            f"{prefix}ELASTICSEARCH_USERNAME": "elasticsearch_username",
            f"{prefix}ELASTICSEARCH_PASSWORD": "elasticsearch_password",
            f"{prefix}PI_SSH_USER": "pi_ssh_user",
            f"{prefix}PI_SSH_PASSWORD": "pi_ssh_password",
            f"{prefix}PI_SUDO_PASSWORD": "pi_sudo_password",
        }
        
        loaded = 0
        for env_var, secret_name in env_mapping.items():
            value = os.getenv(env_var)
            if value:
                if self.set_secret(secret_name, value):
                    loaded += 1
                    logger.info(f"Loaded {secret_name} from environment variable {env_var}")
        
        return loaded
    
    def load_secrets_from_file(self, file_path: Path) -> int:
        """
        Charge les secrets depuis un fichier JSON.
        
        Utile pour la migration depuis secret.json.
        
        Args:
            file_path: Chemin vers le fichier JSON
            
        Returns:
            Nombre de secrets chargés
        """
        if not file_path.exists():
            logger.warning(f"Secret file not found: {file_path}")
            return 0
        
        try:
            import json
            
            with open(file_path) as f:
                secrets_data = json.load(f)
            
            # Mapper les clés du fichier JSON aux noms de secrets
            file_mapping = {
                "aws_access_key_id": "aws_access_key_id",
                "aws_secret_access_key": "aws_secret_access_key",
                "aws_session_token": "aws_session_token",
                "tailscale_api_key": "tailscale_api_key",
                "tailscale_oauth_client_id": "tailscale_oauth_client_id",
                "tailscale_oauth_client_secret": "tailscale_oauth_client_secret",
                "elasticsearch_username": "elasticsearch_username",
                "elasticsearch_password": "elasticsearch_password",
                "pi_ssh_user": "pi_ssh_user",
                "pi_ssh_password": "pi_ssh_password",
                "pi_sudo_password": "pi_sudo_password",
            }
            
            loaded = 0
            for file_key, secret_name in file_mapping.items():
                if file_key in secrets_data:
                    value = secrets_data[file_key]
                    if value and self.set_secret(secret_name, str(value)):
                        loaded += 1
                        logger.info(f"Loaded {secret_name} from file")
            
            return loaded
            
        except Exception as e:
            logger.error(f"Failed to load secrets from file: {e}")
            return 0
    
    def clear_cache(self) -> None:
        """Vide le cache des secrets."""
        self._secrets_cache.clear()
        logger.debug("Secret cache cleared")
    
    def get_all_secrets(self) -> Dict[str, Optional[str]]:
        """
        Récupère tous les secrets depuis la base de données.
        
        Returns:
            Dictionnaire avec tous les secrets
        """
        all_secrets = {}
        secret_names = [
            "aws_access_key_id",
            "aws_secret_access_key",
            "aws_session_token",
            "tailscale_api_key",
            "tailscale_oauth_client_id",
            "tailscale_oauth_client_secret",
            "elasticsearch_username",
            "elasticsearch_password",
            "pi_ssh_user",
            "pi_ssh_password",
            "pi_sudo_password",
        ]
        
        for secret_name in secret_names:
            all_secrets[secret_name] = self.get_secret(secret_name)
        
        return all_secrets
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retourne le statut actuel du gestionnaire de secrets.
        
        Returns:
            Dictionnaire avec le statut
        """
        return {
            "db_initialized": self._db_initialized,
            "cached_secrets_count": len(self._secrets_cache),
            "available_secrets": list(self.get_all_secrets().keys()),
        }


# Instance globale pour faciliter l'utilisation
secret_manager = SecretManager()
