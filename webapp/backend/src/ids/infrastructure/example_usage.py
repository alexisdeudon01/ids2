"""
Exemples d'utilisation des modules d'infrastructure.

Ce fichier montre comment utiliser DependencyManager, DockerOrchestrator et SecretManager.
"""

from pathlib import Path

from ids.infrastructure import (
    dependency_manager,
    docker_orchestrator,
    secret_manager,
)


def example_dependency_manager():
    """Exemple d'utilisation de DependencyManager."""
    print("=== DependencyManager Example ===\n")
    
    # Vérifier les prérequis Python
    python_prereq = dependency_manager.check_python_prerequisites()
    print(f"Python prerequisites: {python_prereq}")
    
    # Vérifier les prérequis Docker
    docker_prereq = dependency_manager.check_docker_prerequisites()
    print(f"Docker prerequisites: {docker_prereq}\n")
    
    # Installer les dépendances Python
    if python_prereq.get("python_version") and python_prereq.get("pip"):
        print("Installing Python requirements...")
        success = dependency_manager.install_python_requirements()
        print(f"Installation {'successful' if success else 'failed'}\n")
    
    # Enregistrer les dépendances d'un module
    dependency_manager.register_module_dependencies(
        "ids.suricata.manager",
        ["redis", "boto3", "yaml"]
    )
    
    # Obtenir le statut
    status = dependency_manager.get_status()
    print(f"DependencyManager status: {status}\n")


def example_docker_orchestrator():
    """Exemple d'utilisation de DockerOrchestrator."""
    print("=== DockerOrchestrator Example ===\n")
    
    # Vérifier les prérequis
    prereq = docker_orchestrator.check_prerequisites()
    print(f"Docker prerequisites: {prereq}\n")
    
    if not prereq.get("docker_installed"):
        print("Docker is not installed. Skipping Docker operations.\n")
        return
    
    # Analyser la communication entre services
    comm_info = docker_orchestrator.get_service_communication_info()
    print(f"Network: {comm_info.get('network')}")
    print(f"Services: {list(comm_info.get('services', {}).keys())}\n")
    
    # Construire les images (décommenter pour exécuter)
    # print("Building Docker images...")
    # success = docker_orchestrator.build_all_images()
    # print(f"Build {'successful' if success else 'failed'}\n")
    
    # Démarrer les services (décommenter pour exécuter)
    # print("Starting Docker services...")
    # success = docker_orchestrator.start_services()
    # print(f"Services {'started' if success else 'failed to start'}\n")
    
    # Obtenir le statut
    status = docker_orchestrator.get_status()
    print(f"DockerOrchestrator status: {status}\n")


def example_secret_manager():
    """Exemple d'utilisation de SecretManager."""
    print("=== SecretManager Example ===\n")
    
    # Définir un secret
    print("Setting secrets...")
    secret_manager.set_secret("aws_access_key_id", "AKIAIOSFODNN7EXAMPLE")
    secret_manager.set_secret("aws_secret_access_key", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    print("Secrets set\n")
    
    # Récupérer un secret
    aws_key = secret_manager.get_secret("aws_access_key_id")
    print(f"AWS Access Key ID: {aws_key[:10]}... (truncated)\n")
    
    # Charger depuis les variables d'environnement
    print("Loading secrets from environment variables...")
    loaded = secret_manager.load_secrets_from_env(prefix="IDS_")
    print(f"Loaded {loaded} secrets from environment\n")
    
    # Charger depuis un fichier JSON (si existe)
    secret_file = Path("secret.json")
    if secret_file.exists():
        print(f"Loading secrets from {secret_file}...")
        loaded = secret_manager.load_secrets_from_file(secret_file)
        print(f"Loaded {loaded} secrets from file\n")
    
    # Récupérer tous les secrets
    all_secrets = secret_manager.get_all_secrets()
    print(f"Total secrets available: {len([v for v in all_secrets.values() if v])}\n")
    
    # Obtenir le statut
    status = secret_manager.get_status()
    print(f"SecretManager status: {status}\n")


def example_integration():
    """Exemple d'intégration complète."""
    print("=== Integration Example ===\n")
    
    # 1. Initialiser la base de données et charger les secrets
    from ids.storage import database
    database.init_db()
    secret_manager.load_secrets_from_env()
    
    # 2. Vérifier et installer les dépendances
    python_prereq = dependency_manager.check_python_prerequisites()
    if python_prereq.get("python_version") and python_prereq.get("pip"):
        dependency_manager.install_python_requirements()
    
    # 3. Vérifier et démarrer Docker
    docker_prereq = docker_orchestrator.check_prerequisites()
    if docker_prereq.get("docker_installed") and docker_prereq.get("docker_running"):
        docker_orchestrator.build_all_images()
        docker_orchestrator.start_services()
    
    # 4. Utiliser les secrets dans le code
    aws_key = secret_manager.get_secret("aws_access_key_id")
    if aws_key:
        print(f"Using AWS key: {aws_key[:10]}...")
    
    print("\nIntegration complete!")


if __name__ == "__main__":
    print("=" * 70)
    print("INFRASTRUCTURE MODULES - EXAMPLES")
    print("=" * 70)
    print()
    
    # Exécuter les exemples (décommenter ceux que vous voulez tester)
    # example_dependency_manager()
    # example_docker_orchestrator()
    # example_secret_manager()
    # example_integration()
    
    print("Décommentez les exemples dans le code pour les exécuter.")
