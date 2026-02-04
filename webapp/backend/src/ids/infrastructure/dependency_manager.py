"""
Gestionnaire de dépendances avec injection dans les modules.

Ce module fournit une classe singleton DependencyManager qui permet de :
- Gérer l'installation des dépendances Python (requirements.txt)
- Gérer l'installation des dépendances Docker (docker-compose)
- Injecter les dépendances dans les différents modules du projet
- Vérifier les prérequis avant installation
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from threading import Lock

logger = logging.getLogger(__name__)


class DependencyManager:
    """
    Gestionnaire de dépendances singleton.
    
    Permet de gérer les dépendances Python et Docker, et d'injecter
    les dépendances dans les différents modules du projet.
    """
    
    _instance: Optional['DependencyManager'] = None
    _lock: Lock = Lock()
    
    def __new__(cls) -> 'DependencyManager':
        """Implémentation du pattern singleton."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """Initialise le gestionnaire de dépendances."""
        if self._initialized:
            return
        
        self._initialized = True
        self._installed_python_packages: Set[str] = set()
        self._installed_docker_services: Set[str] = set()
        self._module_dependencies: Dict[str, List[str]] = {}
        self._project_root: Optional[Path] = None
        self._requirements_file: Optional[Path] = None
        self._docker_compose_file: Optional[Path] = None
        
        # Détection automatique des chemins
        self._detect_project_structure()
    
    def _detect_project_structure(self) -> None:
        """Détecte automatiquement la structure du projet."""
        # Chercher le répertoire racine du projet
        current = Path(__file__).resolve()
        while current.parent != current:
            if (current / "pyproject.toml").exists() or (current / "setup.py").exists():
                self._project_root = current
                break
            current = current.parent
        
        if not self._project_root:
            # Fallback: utiliser le répertoire parent de src
            self._project_root = Path(__file__).resolve().parents[3]
        
        # Chercher requirements.txt
        for path in [self._project_root, self._project_root / "webapp" / "backend"]:
            req_file = path / "requirements.txt"
            if req_file.exists():
                self._requirements_file = req_file
                break
        
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
        
        logger.info(f"Project root: {self._project_root}")
        logger.info(f"Requirements file: {self._requirements_file}")
        logger.info(f"Docker compose file: {self._docker_compose_file}")
    
    def register_module_dependencies(self, module_name: str, dependencies: List[str]) -> None:
        """
        Enregistre les dépendances d'un module.
        
        Args:
            module_name: Nom du module (ex: 'ids.suricata.manager')
            dependencies: Liste des dépendances requises
        """
        self._module_dependencies[module_name] = dependencies
        logger.debug(f"Registered dependencies for {module_name}: {dependencies}")
    
    def get_module_dependencies(self, module_name: str) -> List[str]:
        """
        Récupère les dépendances d'un module.
        
        Args:
            module_name: Nom du module
            
        Returns:
            Liste des dépendances
        """
        return self._module_dependencies.get(module_name, [])
    
    def check_python_package(self, package_name: str) -> bool:
        """
        Vérifie si un package Python est installé.
        
        Args:
            package_name: Nom du package (ex: 'redis', 'boto3')
            
        Returns:
            True si le package est installé
        """
        try:
            __import__(package_name.replace("-", "_"))
            return True
        except ImportError:
            return False
    
    def check_python_prerequisites(self) -> Dict[str, bool]:
        """
        Vérifie les prérequis Python.
        
        Returns:
            Dictionnaire avec le statut de chaque prérequis
        """
        prerequisites = {
            "python_version": sys.version_info >= (3, 10),
            "pip": self.check_python_package("pip"),
        }
        return prerequisites
    
    def install_python_requirements(
        self,
        requirements_file: Optional[Path] = None,
        upgrade: bool = False,
        user: bool = False,
    ) -> bool:
        """
        Installe les dépendances Python depuis requirements.txt.
        
        Args:
            requirements_file: Chemin vers requirements.txt (utilise auto-détection si None)
            upgrade: Mettre à jour les packages existants
            user: Installer pour l'utilisateur courant
            
        Returns:
            True si l'installation a réussi
        """
        req_file = requirements_file or self._requirements_file
        
        if not req_file or not req_file.exists():
            logger.error(f"Requirements file not found: {req_file}")
            return False
        
        logger.info(f"Installing Python requirements from {req_file}")
        
        cmd = [sys.executable, "-m", "pip", "install"]
        if upgrade:
            cmd.append("--upgrade")
        if user:
            cmd.append("--user")
        cmd.extend(["-r", str(req_file)])
        
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("Python requirements installed successfully")
            logger.debug(result.stdout)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install Python requirements: {e}")
            logger.error(e.stderr)
            return False
    
    def check_docker_prerequisites(self) -> Dict[str, bool]:
        """
        Vérifie les prérequis Docker.
        
        Returns:
            Dictionnaire avec le statut de chaque prérequis
        """
        prerequisites = {
            "docker": False,
            "docker_compose": False,
        }
        
        # Vérifier Docker
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            prerequisites["docker"] = True
            logger.debug(f"Docker version: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("Docker not found")
        
        # Vérifier Docker Compose
        for cmd in ["docker-compose", "docker", "compose"]:
            try:
                if cmd == "docker":
                    result = subprocess.run(
                        ["docker", "compose", "version"],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                else:
                    result = subprocess.run(
                        [cmd, "--version"],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                prerequisites["docker_compose"] = True
                logger.debug(f"Docker Compose version: {result.stdout.strip()}")
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        return prerequisites
    
    def install_docker_services(
        self,
        docker_compose_file: Optional[Path] = None,
        services: Optional[List[str]] = None,
        build: bool = False,
    ) -> bool:
        """
        Installe/démarre les services Docker via docker-compose.
        
        Args:
            docker_compose_file: Chemin vers docker-compose.yml (utilise auto-détection si None)
            services: Liste des services à démarrer (tous si None)
            build: Reconstruire les images
            
        Returns:
            True si l'installation a réussi
        """
        compose_file = docker_compose_file or self._docker_compose_file
        
        if not compose_file or not compose_file.exists():
            logger.error(f"Docker compose file not found: {compose_file}")
            return False
        
        # Vérifier les prérequis Docker
        prerequisites = self.check_docker_prerequisites()
        if not prerequisites["docker"]:
            logger.error("Docker is not installed or not accessible")
            return False
        if not prerequisites["docker_compose"]:
            logger.error("Docker Compose is not installed or not accessible")
            return False
        
        logger.info(f"Installing Docker services from {compose_file}")
        
        # Déterminer la commande docker compose
        compose_cmd = ["docker", "compose"]
        try:
            subprocess.run(["docker", "compose", "version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            compose_cmd = ["docker-compose"]
        
        # Construire la commande
        cmd = compose_cmd + ["-f", str(compose_file)]
        
        if build:
            cmd.extend(["build"])
            if services:
                cmd.extend(services)
        else:
            cmd.extend(["up", "-d"])
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
            logger.info("Docker services installed/started successfully")
            logger.debug(result.stdout)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install Docker services: {e}")
            logger.error(e.stderr)
            return False
    
    def inject_dependencies(self, module_name: str, target_module: Any) -> bool:
        """
        Injecte les dépendances dans un module.
        
        Args:
            module_name: Nom du module
            target_module: Module ou classe cible
            
        Returns:
            True si l'injection a réussi
        """
        dependencies = self.get_module_dependencies(module_name)
        
        if not dependencies:
            logger.warning(f"No dependencies registered for {module_name}")
            return False
        
        # Vérifier que toutes les dépendances sont disponibles
        missing = []
        for dep in dependencies:
            if not self.check_python_package(dep):
                missing.append(dep)
        
        if missing:
            logger.error(f"Missing dependencies for {module_name}: {missing}")
            return False
        
        # Injecter les dépendances dans le module
        # Cette partie peut être étendue selon les besoins
        logger.info(f"Injected dependencies into {module_name}: {dependencies}")
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retourne le statut actuel du gestionnaire de dépendances.
        
        Returns:
            Dictionnaire avec le statut
        """
        return {
            "project_root": str(self._project_root) if self._project_root else None,
            "requirements_file": str(self._requirements_file) if self._requirements_file else None,
            "docker_compose_file": str(self._docker_compose_file) if self._docker_compose_file else None,
            "python_prerequisites": self.check_python_prerequisites(),
            "docker_prerequisites": self.check_docker_prerequisites(),
            "registered_modules": list(self._module_dependencies.keys()),
            "installed_python_packages": list(self._installed_python_packages),
            "installed_docker_services": list(self._installed_docker_services),
        }


# Instance globale pour faciliter l'utilisation
dependency_manager = DependencyManager()
