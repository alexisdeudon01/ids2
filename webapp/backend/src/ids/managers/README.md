# Gestionnaires d'Infrastructure IDS

Ce module fournit des gestionnaires complets pour l'infrastructure IDS :

## 📡 TailscaleManager

Gestion complète du réseau Tailscale mesh.

### Fonctionnalités

- ✅ Liste/ajout/suppression de devices
- ✅ Gestion des auth keys (création, révocation)
- ✅ Gestion des tags et ACLs
- ✅ Tests de connectivité (ping)
- ✅ Monitoring du réseau
- ✅ Autorisation de devices

### Utilisation

```python
from ids.managers import TailscaleManager

async with TailscaleManager(api_key="tskey-api-...", tailnet="example.com") as manager:
    # Lister les devices
    devices = await manager.list_devices()
    for device in devices:
        print(f"{device.name}: {device.addresses[0]} - {'🟢' if device.online else '🔴'}")
    
    # Trouver un device par IP
    device = await manager.find_device_by_ip("100.118.244.54")
    if device:
        print(f"Found: {device.name}")
    
    # Ping un device
    latency = manager.ping_device("100.118.244.54", count=4)
    print(f"Latency: {latency:.2f}ms")
    
    # Créer une auth key
    key = await manager.create_auth_key(
        description="Production server",
        reusable=True,
        preauthorized=True,
        tags=["tag:server", "tag:production"]
    )
    print(f"New key: {key}")
    
    # Autoriser un device
    await manager.authorize_device(device.device_id)
    
    # Définir des tags
    await manager.set_device_tags(device.device_id, ["tag:raspberry-pi", "tag:ids"])
    
    # Supprimer un device
    await manager.delete_device(device.device_id)
    
    # Statut du réseau
    status = await manager.get_network_status()
    print(f"Total devices: {status['total_devices']}")
    print(f"Online: {status['online_devices']}")
```

### Bibliothèque utilisée

- `tailscale>=0.6.0` - Client officiel Python pour l'API Tailscale

---

## 🔍 OpenSearchDomainManager

Gestion complète des domaines AWS OpenSearch.

### Fonctionnalités

- ✅ Création/suppression de domaines
- ✅ Monitoring du statut
- ✅ Gestion des index
- ✅ Tests de connectivité
- ✅ Scaling (instances, storage)
- ✅ Liste des domaines

### Utilisation

```python
from ids.managers import OpenSearchDomainManager

manager = OpenSearchDomainManager(
    aws_access_key_id="AKIA...",
    aws_secret_access_key="...",
    region="eu-central-1"
)

# Créer un domaine
status = manager.create_domain(
    domain_name="suricata-prod",
    instance_type="t3.small.search",
    instance_count=1,
    volume_size_gb=10,
    engine_version="OpenSearch_2.11",
    wait=True,  # Attendre que le domaine soit prêt
    timeout=1800
)
print(f"Endpoint: {status.endpoint}")

# Lister les domaines
domains = manager.list_domains()
for domain in domains:
    status = manager.get_domain_status(domain)
    print(f"{domain}: {status.endpoint}")

# Tester la connectivité
is_online = manager.ping_domain(status.endpoint)
print(f"Domain accessible: {is_online}")

# Lister les index
indexes = manager.list_indexes(status.endpoint)
for idx in indexes:
    print(f"{idx.name}: {idx.doc_count} docs, {idx.health}")

# Créer un index
manager.create_index(
    endpoint=status.endpoint,
    index_name="suricata-logs-2024",
    mappings={
        "properties": {
            "timestamp": {"type": "date"},
            "src_ip": {"type": "ip"},
            "dest_ip": {"type": "ip"},
        }
    }
)

# Supprimer un domaine
manager.delete_domain("old-domain")
```

### Bibliothèques utilisées

- `boto3>=1.26.0` - AWS SDK
- `opensearch-py>=2.4.0` - Client OpenSearch
- `requests-aws4auth>=1.2.0` - Authentification AWS SigV4

---

## 🍓 RaspberryPiManager

Gestion complète du Raspberry Pi via SSH.

### Fonctionnalités

- ✅ Connexion SSH sécurisée
- ✅ Exécution de commandes à distance
- ✅ Monitoring système (CPU, RAM, température, disque)
- ✅ Gestion des services systemd
- ✅ Gestion Docker (conteneurs, compose)
- ✅ Transfert de fichiers (SFTP, rsync)
- ✅ Informations réseau

### Utilisation

```python
from ids.managers import RaspberryPiManager

with RaspberryPiManager(
    host="100.118.244.54",
    user="pi",
    ssh_key_path="~/.ssh/pi_ssh_key"
) as pi:
    # Infos système
    info = pi.get_system_info()
    print(f"Model: {info.model}")
    print(f"Temperature: {info.cpu_temperature}°C")
    print(f"Load: {info.load_average}")
    
    # Exécuter une commande
    exit_code, stdout, stderr = pi.run_command("uptime")
    print(stdout)
    
    # Avec sudo
    exit_code, stdout, stderr = pi.run_command("systemctl status docker", sudo=True)
    
    # Monitoring
    cpu_usage = pi.get_cpu_usage()
    mem_usage = pi.get_memory_usage()
    disk_usage = pi.get_disk_usage("/")
    temp = pi.get_temperature()
    
    print(f"CPU: {cpu_usage:.1f}%")
    print(f"Memory: {mem_usage['usage_percent']:.1f}%")
    print(f"Disk: {disk_usage['usage_percent']:.1f}%")
    print(f"Temp: {temp:.1f}°C")
    
    # Services systemd
    status = pi.get_service_status("ids2-agent.service")
    print(f"Active: {status.active}, Running: {status.running}")
    
    pi.restart_service("ids2-agent.service")
    pi.start_service("suricata.service")
    pi.stop_service("vector.service")
    
    # Docker
    containers = pi.list_containers()
    for container in containers:
        print(f"{container.name}: {container.status}")
    
    pi.start_container("vector")
    pi.restart_container("redis")
    pi.docker_compose_up("/opt/ids/docker")
    
    # Transfert de fichiers
    pi.upload_file("config.yaml", "/opt/ids/config.yaml")
    pi.download_file("/var/log/ids2-agent.log", "./agent.log")
    pi.upload_directory("./deploy", "/opt/ids/deploy")
    
    # Gestion des permissions
    pi.ensure_directory("/opt/ids/logs", sudo=True)
    pi.set_permissions("/opt/ids", "755", sudo=True)
    pi.set_owner("/opt/ids", "pi:pi", sudo=True)
```

### Bibliothèques utilisées

- `paramiko>=3.0.0` - Client SSH Python
- `gpiozero>=2.0.0` - GPIO Raspberry Pi (optionnel, seulement sur le Pi)

---

## 🚀 Script CLI unifié

Un script CLI est fourni pour utiliser tous les gestionnaires :

```bash
# Tailscale
python scripts/manage_infrastructure.py tailscale list-devices
python scripts/manage_infrastructure.py tailscale ping 100.118.244.54
python scripts/manage_infrastructure.py tailscale create-key

# OpenSearch
python scripts/manage_infrastructure.py opensearch create-domain suricata-prod
python scripts/manage_infrastructure.py opensearch list-domains
python scripts/manage_infrastructure.py opensearch list-indexes search-suricata-prod-xxx.eu-central-1.es.amazonaws.com

# Raspberry Pi
python scripts/manage_infrastructure.py pi info
python scripts/manage_infrastructure.py pi services
python scripts/manage_infrastructure.py pi docker-ps
python scripts/manage_infrastructure.py pi restart-service ids2-agent.service
```

---

## 📦 Installation des dépendances

```bash
pip install -r requirements.txt
```

Les dépendances incluent :
- `tailscale>=0.6.0`
- `boto3>=1.26.0`
- `opensearch-py>=2.4.0`
- `requests-aws4auth>=1.2.0`
- `paramiko>=3.0.0`
- `gpiozero>=2.0.0` (optionnel)

---

## 🔐 Sécurité

- Les clés API ne sont jamais loggées
- Utilisation de `getpass` pour les entrées sensibles
- Connexions SSH sécurisées avec clés
- Authentification AWS avec SigV4
- Support des IAM roles

---

## 🧪 Tests

Des tests unitaires sont disponibles dans `tests/unit/` pour chaque gestionnaire.

```bash
pytest tests/unit/test_tailscale_manager.py
pytest tests/unit/test_opensearch_manager.py
pytest tests/unit/test_raspberry_pi_manager.py
```

---

## 📚 Ressources

- [Tailscale API Docs](https://tailscale.com/api)
- [AWS OpenSearch Docs](https://docs.aws.amazon.com/opensearch-service/)
- [Paramiko Docs](https://docs.paramiko.org/)
- [gpiozero Docs](https://gpiozero.readthedocs.io/)
