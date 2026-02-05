# Infrastructure Modules

Ce package contient trois modules singleton pour gérer l'infrastructure du projet IDS.

## Modules

### 1. DependencyManager

Gestionnaire de dépendances avec injection dans les modules.

**Fonctionnalités:**
- Installation des dépendances Python depuis `requirements.txt`
- Installation des services Docker via `docker-compose.yml`
- Vérification des prérequis (Python, pip, Docker, Docker Compose)
- Enregistrement et injection de dépendances dans les modules

**Exemple d'utilisation:**

```python
from ids.infrastructure import dependency_manager

# Vérifier les prérequis
python_prereq = dependency_manager.check_python_prerequisites()
docker_prereq = dependency_manager.check_docker_prerequisites()

# Installer les dépendances Python
if python_prereq.get("python_version") and python_prereq.get("pip"):
    dependency_manager.install_python_requirements()

# Installer les services Docker
if docker_prereq.get("docker_installed") and docker_prereq.get("docker_running"):
    dependency_manager.install_docker_services()

# Enregistrer les dépendances d'un module
dependency_manager.register_module_dependencies(
    "ids.suricata.manager",
    ["redis", "boto3", "yaml"]
)

# Injecter les dépendances dans un module
dependency_manager.inject_dependencies("ids.suricata.manager", my_module)
```

### 2. DockerOrchestrator

Orchestrateur Docker pour gérer les builds et services.

**Fonctionnalités:**
- Vérification des prérequis Docker
- Build d'images Docker individuelles ou depuis docker-compose
- Démarrage/arrêt des services Docker
- Analyse de la communication entre services
- Attente de disponibilité des services

**Exemple d'utilisation:**

```python
from ids.infrastructure import docker_orchestrator

# Vérifier les prérequis
prereq = docker_orchestrator.check_prerequisites()
if not prereq.get("docker_installed"):
    print("Docker n'est pas installé")

# Construire toutes les images
docker_orchestrator.build_all_images()

# Démarrer les services
docker_orchestrator.start_services()

# Analyser la communication entre services
comm_info = docker_orchestrator.get_service_communication_info()
print(f"Réseau: {comm_info['network']}")
print(f"Services: {list(comm_info['services'].keys())}")

# Attendre qu'un service soit prêt
docker_orchestrator.wait_for_service("redis", timeout=60)

# Obtenir le statut
status = docker_orchestrator.get_status()
```

### 3. SecretManager

Gestionnaire de secrets avec stockage en base de données.

**Fonctionnalités:**
- Stockage des secrets dans la base de données SQLite
- Récupération des secrets depuis la base de données
- Migration depuis variables d'environnement ou fichier JSON
- Cache pour améliorer les performances
- Plus besoin de variables d'environnement ou fichiers secrets.json

**Exemple d'utilisation:**

```python
from ids.infrastructure import secret_manager
from pathlib import Path

# Définir un secret
secret_manager.set_secret("aws_access_key_id", "AKIAIOSFODNN7EXAMPLE")

# Récupérer un secret
aws_key = secret_manager.get_secret("aws_access_key_id")
if not aws_key:
    print("Secret non trouvé")

# Charger depuis les variables d'environnement
loaded = secret_manager.load_secrets_from_env(prefix="IDS_")
print(f"{loaded} secrets chargés depuis l'environnement")

# Charger depuis un fichier JSON (migration depuis secret.json)
loaded = secret_manager.load_secrets_from_file(Path("secret.json"))
print(f"{loaded} secrets chargés depuis le fichier")

# Définir plusieurs secrets en une fois
secrets = {
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "tailscale_api_key": "tskey-xxx",
}
results = secret_manager.set_secrets_batch(secrets)

# Récupérer tous les secrets
all_secrets = secret_manager.get_all_secrets()

# Obtenir le statut
status = secret_manager.get_status()
```

## Migration depuis l'ancien système

### Avant (avec variables d'environnement)

```python
import os

aws_key = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
```

### Après (avec SecretManager)

```python
from ids.infrastructure import secret_manager

aws_key = secret_manager.get_secret("aws_access_key_id")
aws_secret = secret_manager.get_secret("aws_secret_access_key")
```

### Migration depuis secret.json

```python
from ids.infrastructure import secret_manager
from pathlib import Path

# Charger automatiquement depuis secret.json
secret_manager.load_secrets_from_file(Path("secret.json"))
```

## Intégration avec setup.py

La fonction `setup_infrastructure()` dans `ids.dashboard.setup` a été étendue pour utiliser tous ces modules:

```python
from ids.dashboard.setup import setup_infrastructure

results = await setup_infrastructure(
    tailnet="example.com",
    tailscale_api_key="tskey-xxx",
    opensearch_domain="suricata-prod",
    config_path="config.yaml",
    init_database=True,          # Initialiser la base de données
    load_secrets=True,            # Charger les secrets
    install_dependencies=True,    # Installer les dépendances Python
    start_docker_services=True,   # Démarrer les services Docker
)

print(results)
```

## Pattern Singleton

Tous les modules utilisent le pattern singleton pour garantir une seule instance:

```python
from ids.infrastructure import dependency_manager, docker_orchestrator, secret_manager

# Ces instances sont les mêmes partout dans le code
manager1 = dependency_manager
manager2 = dependency_manager
assert manager1 is manager2  # True
```

## Communication Docker

Voir `DOCKER_COMMUNICATION.md` pour les détails sur la communication entre services Docker.
