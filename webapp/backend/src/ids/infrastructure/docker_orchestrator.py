"""
Orchestrateur Docker avec pattern singleton.

Ce module fournit une classe singleton DockerOrchestrator qui permet de :
- Gérer les builds Docker
- Vérifier les prérequis Docker
- Installer et démarrer les services Docker
- Gérer la communication entre les conteneurs Docker
"""

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from threading import Lock

logger = logging.getLogger(__name__)


class DockerOrchestrator:
    """
    Orchestrateur Docker singleton.
    
    Gère les builds, installations et vérifications Docker.
    """
    
    _instance: Optional['DockerOrchestrator'] = None
    _lock: Lock = Lock()
    
    def __new__(cls) -> 'DockerOrchestrator':
        """Implémentation du pattern singleton."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized: bool = False
        return cls._instance
    
    def __init__(self) -> None:
        """Initialise l'orchestrateur Docker."""
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized: bool = True
        self._built_images: Set[str] = set()
        self._running_containers: Set[str] = set()
        self._project_root: Optional[Path] = None
        self._docker_compose_file: Optional[Path] = None
        self._docker_network: Optional[str] = None
        
        # Détection automatique
        self._detect_docker_structure()
    
    def _detect_docker_structure(self) -> None:
        """Détecte automatiquement la structure Docker."""
        current = Path(__file__).resolve()
        while current.parent != current:
            if (current / "docker-compose.yml").exists() or (current / "pyproject.toml").exists():
                self._project_root = current
                break
            current = current.parent
        
        if not self._project_root:
            self._project_root = Path(__file__).resolve().parents[3]
        
        # Chercher docker-compose.yml
        for path in [
            self._project_root / "webapp" / "backend" / "docker",
            self._project_root / "docker",
            self._project_root,
        ]:
            compose_file = path / "docker-compose.yml"
            if compose_file.exists():
                self._docker_compose_file = compose_file
                break
        
        # Détecter le réseau Docker (généralement défini dans docker-compose.yml)
        if self._docker_compose_file:
            self._docker_network = self._extract_network_name()
        
        logger.info(f"Docker compose file: {self._docker_compose_file}")
        logger.info(f"Docker network: {self._docker_network}")
    
    def _extract_network_name(self) -> Optional[str]:
        """Extrait le nom du réseau depuis docker-compose.yml."""
        if not self._docker_compose_file:
            return None
        
        try:
            import yaml
            with open(self._docker_compose_file) as f:
                compose_data = yaml.safe_load(f)
            
            # Chercher le réseau défini
            if "networks" in compose_data:
                networks = compose_data["networks"]
                if networks:
                    # Retourner le premier réseau trouvé
                    return list(networks.keys())[0]
            
            # Si pas de réseau explicite, docker-compose crée un réseau par défaut
            # basé sur le nom du répertoire parent
            if self._docker_compose_file.parent:
                return f"{self._docker_compose_file.parent.name}_default"
        except Exception as e:
            logger.warning(f"Could not extract network name: {e}")
        
        return None
    
    def check_prerequisites(self) -> Dict[str, Any]:
        """
        Vérifie les prérequis Docker.
        
        Returns:
            Dictionnaire avec le statut de chaque prérequis
        """
        prerequisites = {
            "docker_installed": False,
            "docker_running": False,
            "docker_compose_available": False,
            "docker_compose_file_exists": self._docker_compose_file is not None and self._docker_compose_file.exists(),
            "permissions": False,
        }
        
        # Vérifier Docker installé
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            prerequisites["docker_installed"] = True
            logger.debug(f"Docker version: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("Docker is not installed")
            return prerequisites
        
        # Vérifier Docker en cours d'exécution
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                check=True,
            )
            prerequisites["docker_running"] = True
            prerequisites["permissions"] = True
        except subprocess.CalledProcessError:
            logger.warning("Docker is not running or permissions denied")
        except FileNotFoundError:
            pass
        
        # Vérifier Docker Compose
        for cmd in [["docker", "compose"], ["docker-compose"]]:
            try:
                result = subprocess.run(
                    cmd + ["version"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                prerequisites["docker_compose_available"] = True
                logger.debug(f"Docker Compose version: {result.stdout.strip()}")
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        return prerequisites
    
    def build_image(
        self,
        dockerfile_path: Path,
        image_name: str,
        build_args: Optional[Dict[str, str]] = None,
        tag: Optional[str] = None,
    ) -> bool:
        """
        Construit une image Docker.
        
        Args:
            dockerfile_path: Chemin vers le Dockerfile
            image_name: Nom de l'image
            build_args: Arguments de build
            tag: Tag de l'image (utilise image_name si None)
            
        Returns:
            True si le build a réussi
        """
        if not dockerfile_path.exists():
            logger.error(f"Dockerfile not found: {dockerfile_path}")
            return False
        
        tag = tag or image_name
        logger.info(f"Building Docker image: {tag}")
        
        cmd = ["docker", "build", "-t", tag]
        
        if build_args:
            for key, value in build_args.items():
                cmd.extend(["--build-arg", f"{key}={value}"])
        
        cmd.append(str(dockerfile_path.parent))
        
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            self._built_images.add(tag)
            logger.info(f"Successfully built image: {tag}")
            logger.debug(result.stdout)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to build image {tag}: {e}")
            logger.error(e.stderr)
            return False
    
    def build_all_images(self, compose_file: Optional[Path] = None) -> bool:
        """
        Construit toutes les images depuis docker-compose.yml.
        
        Args:
            compose_file: Chemin vers docker-compose.yml
            
        Returns:
            True si tous les builds ont réussi
        """
        compose_file = compose_file or self._docker_compose_file
        
        if not compose_file or not compose_file.exists():
            logger.error(f"Docker compose file not found: {compose_file}")
            return False
        
        logger.info(f"Building all images from {compose_file}")
        
        # Déterminer la commande docker compose
        compose_cmd = ["docker", "compose"]
        try:
            subprocess.run(["docker", "compose", "version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            compose_cmd = ["docker-compose"]
        
        cmd = compose_cmd + ["-f", str(compose_file), "build"]
        
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                cwd=compose_file.parent,
            )
            logger.info("All images built successfully")
            logger.debug(result.stdout)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to build images: {e}")
            logger.error(e.stderr)
            return False
    
    def start_services(
        self,
        compose_file: Optional[Path] = None,
        services: Optional[List[str]] = None,
        detach: bool = True,
    ) -> bool:
        """
        Démarre les services Docker.
        
        Args:
            compose_file: Chemin vers docker-compose.yml
            services: Liste des services à démarrer (tous si None)
            detach: Démarrer en arrière-plan
            
        Returns:
            True si le démarrage a réussi
        """
        compose_file = compose_file or self._docker_compose_file
        
        if not compose_file or not compose_file.exists():
            logger.error(f"Docker compose file not found: {compose_file}")
            return False
        
        logger.info(f"Starting Docker services from {compose_file}")
        
        # Déterminer la commande docker compose
        compose_cmd = ["docker", "compose"]
        try:
            subprocess.run(["docker", "compose", "version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            compose_cmd = ["docker-compose"]
        
        cmd = compose_cmd + ["-f", str(compose_file), "up"]
        
        if detach:
            cmd.append("-d")
        
        if services:
            cmd.extend(services)
        
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                cwd=compose_file.parent,
            )
            logger.info("Docker services started successfully")
            logger.debug(result.stdout)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start services: {e}")
            logger.error(e.stderr)
            return False
    
    def stop_services(
        self,
        compose_file: Optional[Path] = None,
        services: Optional[List[str]] = None,
    ) -> bool:
        """
        Arrête les services Docker.
        
        Args:
            compose_file: Chemin vers docker-compose.yml
            services: Liste des services à arrêter (tous si None)
            
        Returns:
            True si l'arrêt a réussi
        """
        compose_file = compose_file or self._docker_compose_file
        
        if not compose_file or not compose_file.exists():
            logger.error(f"Docker compose file not found: {compose_file}")
            return False
        
        logger.info(f"Stopping Docker services from {compose_file}")
        
        # Déterminer la commande docker compose
        compose_cmd = ["docker", "compose"]
        try:
            subprocess.run(["docker", "compose", "version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            compose_cmd = ["docker-compose"]
        
        cmd = compose_cmd + ["-f", str(compose_file), "down"]
        
        if services:
            cmd.extend(services)
        
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                cwd=compose_file.parent,
            )
            logger.info("Docker services stopped successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to stop services: {e}")
            logger.error(e.stderr)
            return False
    
    def get_container_info(self, container_name: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations d'un conteneur.
        
        Args:
            container_name: Nom du conteneur
            
        Returns:
            Dictionnaire avec les informations du conteneur
        """
        try:
            result = subprocess.run(
                ["docker", "inspect", container_name],
                capture_output=True,
                text=True,
                check=True,
            )
            containers = json.loads(result.stdout)
            if containers:
                return containers[0]
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get container info for {container_name}: {e}")
        
        return None
    
    def get_service_communication_info(self) -> Dict[str, Any]:
        """
        Récupère les informations de communication entre services Docker.
        
        Cette fonction analyse docker-compose.yml pour déterminer comment
        les services communiquent entre eux.
        
        Returns:
            Dictionnaire avec les informations de communication
        """
        if not self._docker_compose_file or not self._docker_compose_file.exists():
            return {}
        
        try:
            import yaml
            with open(self._docker_compose_file) as f:
                compose_data = yaml.safe_load(f)
            
            communication_info: Dict[str, Any] = {
                "network": self._docker_network,
                "services": {},
            }
            
            if "services" in compose_data and isinstance(compose_data["services"], dict):
                for service_name, service_config in compose_data["services"].items():
                    if not isinstance(service_config, dict):
                        continue
                    service_info: Dict[str, Any] = {
                        "ports": service_config.get("ports", []),
                        "environment": service_config.get("environment", {}),
                        "depends_on": service_config.get("depends_on", []),
                        "networks": service_config.get("networks", []),
                        "links": service_config.get("links", []),
                    }
                    
                    # Extraire les variables d'environnement qui indiquent la communication
                    env = service_info.get("environment", {})
                    if isinstance(env, dict):
                        # Chercher les URLs/hosts de connexion
                        connection_vars: Dict[str, str] = {}
                        for k, v in env.items():
                            if isinstance(k, str) and isinstance(v, str):
                                if any(keyword in k.lower() for keyword in ["host", "url", "endpoint", "address"]):
                                    connection_vars[k] = v
                        service_info["connection_variables"] = connection_vars
                    
                    communication_info["services"][service_name] = service_info
            
            return communication_info
        except Exception as e:
            logger.error(f"Failed to analyze service communication: {e}")
            return {}
    
    def wait_for_service(
        self,
        service_name: str,
        timeout: int = 60,
        health_check: Optional[str] = None,
    ) -> bool:
        """
        Attend qu'un service soit prêt.
        
        Args:
            service_name: Nom du service
            timeout: Timeout en secondes
            health_check: Commande de health check (optionnelle)
            
        Returns:
            True si le service est prêt
        """
        logger.info(f"Waiting for service {service_name} to be ready...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            container_info = self.get_container_info(service_name)
            
            if container_info:
                state = container_info.get("State", {})
                status = state.get("Status", "")
                
                if status == "running":
                    # Vérifier le health check si fourni
                    if health_check:
                        try:
                            result = subprocess.run(
                                health_check.split(),
                                capture_output=True,
                                check=True,
                                timeout=5,
                            )
                            logger.info(f"Service {service_name} is ready")
                            return True
                        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                            pass
                    else:
                        logger.info(f"Service {service_name} is running")
                        return True
            
            time.sleep(2)
        
        logger.warning(f"Service {service_name} did not become ready within {timeout}s")
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retourne le statut actuel de l'orchestrateur Docker.
        
        Returns:
            Dictionnaire avec le statut
        """
        prerequisites = self.check_prerequisites()
        communication_info = self.get_service_communication_info()
        
        return {
            "prerequisites": prerequisites,
            "docker_compose_file": str(self._docker_compose_file) if self._docker_compose_file else None,
            "docker_network": self._docker_network,
            "built_images": list(self._built_images),
            "running_containers": list(self._running_containers),
            "service_communication": communication_info,
        }


# Instance globale pour faciliter l'utilisation
docker_orchestrator = DockerOrchestrator()
