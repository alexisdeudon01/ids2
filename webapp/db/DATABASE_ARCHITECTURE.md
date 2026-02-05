# Architecture de la Base de Données IDS

## Vue d'ensemble

La base de données utilise **SQLite** avec **SQLAlchemy ORM**. Elle stocke :
- **Configuration** : Paramètres de tous les composants (Suricata, Vector, Docker, etc.)
- **Secrets** : Clés API, mots de passe, credentials (⚠️ en texte clair actuellement)
- **Télémétrie** : Métriques système, alertes, statut des services
- **Historique** : Déploiements, erreurs, logs

**Fichier de base de données** : `data/ids_dashboard.db` (SQLite)

## Structure des Tables

### 1. Configuration (Tables Singleton)

Ces tables utilisent le pattern **singleton** : une seule ligne par table via `get_or_create_singleton()`.

#### `secrets` - Secrets et Credentials
```sql
CREATE TABLE secrets (
    id INTEGER PRIMARY KEY,
    aws_access_key_id TEXT,
    aws_secret_access_key TEXT,
    aws_session_token TEXT,
    tailscale_api_key TEXT,
    tailscale_oauth_client_id TEXT,
    tailscale_oauth_client_secret TEXT,
    elasticsearch_username TEXT,
    elasticsearch_password TEXT,
    pi_ssh_user TEXT,
    pi_ssh_password TEXT,
    pi_sudo_password TEXT,
    created_at DATETIME,
    updated_at DATETIME
);
```

**⚠️ SECURITÉ** : Les secrets sont stockés en **texte clair**. Pour la production :
- Utiliser un chiffrement au niveau des colonnes
- Ou utiliser un gestionnaire de secrets externe (Vault, AWS Secrets Manager)

**Utilisation** : Géré par `SecretManager` (singleton)

#### `aws_config` - Configuration AWS
```sql
CREATE TABLE aws_config (
    id INTEGER PRIMARY KEY,
    region TEXT DEFAULT 'eu-central-1',
    domain_name TEXT DEFAULT 'suricata-prod',
    opensearch_endpoint TEXT,
    created_at DATETIME,
    updated_at DATETIME
);
```

#### `raspberry_pi_config` - Configuration Raspberry Pi
```sql
CREATE TABLE raspberry_pi_config (
    id INTEGER PRIMARY KEY,
    pi_ip TEXT,
    home_net TEXT DEFAULT '192.168.178.0/24',
    network_interface TEXT DEFAULT 'eth0',
    cpu_limit_percent REAL DEFAULT 70.0,
    ram_limit_percent REAL DEFAULT 70.0,
    swap_size_gb INTEGER DEFAULT 2,
    cpu_limit_medium_percent REAL DEFAULT 75.0,
    ram_limit_medium_percent REAL DEFAULT 75.0,
    cpu_limit_high_percent REAL DEFAULT 80.0,
    ram_limit_high_percent REAL DEFAULT 80.0,
    created_at DATETIME,
    updated_at DATETIME
);
```

#### `suricata_config` - Configuration Suricata
```sql
CREATE TABLE suricata_config (
    id INTEGER PRIMARY KEY,
    log_path TEXT DEFAULT '/mnt/ram_logs/eve.json',
    config_path TEXT DEFAULT 'suricata/suricata.yaml',
    rules_path TEXT DEFAULT 'suricata/rules',
    eve_log_payload BOOLEAN DEFAULT 0,
    eve_log_packet BOOLEAN DEFAULT 0,
    eve_log_http BOOLEAN DEFAULT 1,
    eve_log_dns BOOLEAN DEFAULT 1,
    eve_log_tls BOOLEAN DEFAULT 1,
    eve_log_flow BOOLEAN DEFAULT 1,
    eve_log_stats BOOLEAN DEFAULT 1,
    default_log_dir TEXT DEFAULT '/mnt/ram_logs',
    home_net TEXT DEFAULT 'any',
    external_net TEXT DEFAULT 'any',
    http_ports TEXT DEFAULT '80',
    ssh_ports TEXT DEFAULT '22',
    smtp_ports TEXT DEFAULT '25',
    dns_ports TEXT DEFAULT '53',
    tls_ports TEXT DEFAULT '443',
    created_at DATETIME,
    updated_at DATETIME
);
```

#### `vector_config` - Configuration Vector
```sql
CREATE TABLE vector_config (
    id INTEGER PRIMARY KEY,
    index_pattern TEXT DEFAULT 'suricata-ids2-%Y.%m.%d',
    log_read_path TEXT DEFAULT '/mnt/ram_logs/eve.json',
    disk_buffer_max_size TEXT DEFAULT '100 GiB',
    redis_buffer_max_size TEXT DEFAULT '10 GiB',
    opensearch_buffer_max_size TEXT DEFAULT '50 GiB',
    batch_max_events INTEGER DEFAULT 500,
    batch_timeout_secs INTEGER DEFAULT 2,
    read_from TEXT DEFAULT 'beginning',
    fingerprint_bytes INTEGER DEFAULT 1024,
    redis_host TEXT DEFAULT 'redis',
    redis_port INTEGER DEFAULT 6379,
    redis_key TEXT DEFAULT 'vector_logs',
    opensearch_compression TEXT DEFAULT 'gzip',
    opensearch_request_timeout_secs INTEGER DEFAULT 30,
    created_at DATETIME,
    updated_at DATETIME
);
```

#### `redis_config` - Configuration Redis
```sql
CREATE TABLE redis_config (
    id INTEGER PRIMARY KEY,
    host TEXT DEFAULT 'redis',
    port INTEGER DEFAULT 6379,
    db INTEGER DEFAULT 0,
    created_at DATETIME,
    updated_at DATETIME
);
```

#### `prometheus_config` - Configuration Prometheus
```sql
CREATE TABLE prometheus_config (
    id INTEGER PRIMARY KEY,
    port INTEGER DEFAULT 9100,
    docker_port INTEGER DEFAULT 9090,
    update_interval INTEGER DEFAULT 5,
    created_at DATETIME,
    updated_at DATETIME
);
```

#### `grafana_config` - Configuration Grafana
```sql
CREATE TABLE grafana_config (
    id INTEGER PRIMARY KEY,
    docker_port INTEGER DEFAULT 3000,
    created_at DATETIME,
    updated_at DATETIME
);
```

#### `docker_config` - Configuration Docker
```sql
CREATE TABLE docker_config (
    id INTEGER PRIMARY KEY,
    compose_file TEXT DEFAULT 'docker/docker-compose.yml',
    vector_cpu REAL DEFAULT 1.0,
    vector_ram_mb INTEGER DEFAULT 1024,
    redis_cpu REAL DEFAULT 0.5,
    redis_ram_mb INTEGER DEFAULT 512,
    prometheus_cpu REAL DEFAULT 0.2,
    prometheus_ram_mb INTEGER DEFAULT 256,
    grafana_cpu REAL DEFAULT 0.2,
    grafana_ram_mb INTEGER DEFAULT 256,
    cadvisor_cpu REAL DEFAULT 0.1,
    cadvisor_ram_mb INTEGER DEFAULT 64,
    node_exporter_cpu REAL DEFAULT 0.1,
    node_exporter_ram_mb INTEGER DEFAULT 64,
    fastapi_cpu REAL DEFAULT 0.5,
    fastapi_ram_mb INTEGER DEFAULT 256,
    created_at DATETIME,
    updated_at DATETIME
);
```

#### `tailscale_config` - Configuration Tailscale
```sql
CREATE TABLE tailscale_config (
    id INTEGER PRIMARY KEY,
    tailnet TEXT,
    dns_enabled BOOLEAN DEFAULT 1,
    magic_dns BOOLEAN DEFAULT 1,
    exit_node_enabled BOOLEAN DEFAULT 0,
    subnet_routes JSON DEFAULT '[]',
    deployment_mode TEXT DEFAULT 'auto',
    default_tags JSON DEFAULT '["ci", "ids2"]',
    created_at DATETIME,
    updated_at DATETIME
);
```

#### `fastapi_config` - Configuration FastAPI
```sql
CREATE TABLE fastapi_config (
    id INTEGER PRIMARY KEY,
    port INTEGER DEFAULT 8080,
    host TEXT DEFAULT '0.0.0.0',
    log_level TEXT DEFAULT 'INFO',
    created_at DATETIME,
    updated_at DATETIME
);
```

#### `resource_controller_config` - Configuration Resource Controller
```sql
CREATE TABLE resource_controller_config (
    id INTEGER PRIMARY KEY,
    check_interval INTEGER DEFAULT 1,
    throttling_enabled BOOLEAN DEFAULT 1,
    created_at DATETIME,
    updated_at DATETIME
);
```

#### `connectivity_config` - Configuration Connectivity
```sql
CREATE TABLE connectivity_config (
    id INTEGER PRIMARY KEY,
    check_interval INTEGER DEFAULT 10,
    max_retries INTEGER DEFAULT 5,
    initial_backoff REAL DEFAULT 1.0,
    created_at DATETIME,
    updated_at DATETIME
);
```

### 2. Télémétrie et Monitoring

#### `services_status` - Statut des Services
```sql
CREATE TABLE services_status (
    id INTEGER PRIMARY KEY,
    service_name TEXT UNIQUE,
    status TEXT DEFAULT 'unknown' CHECK(status IN ('active', 'inactive', 'failed', 'unknown')),
    enabled BOOLEAN DEFAULT 0,
    last_check DATETIME,
    last_error TEXT,
    created_at DATETIME,
    updated_at DATETIME
);
```

**Services surveillés** : suricata, vector, redis, prometheus, grafana, docker, etc.

#### `system_metrics` - Métriques Système
```sql
CREATE TABLE system_metrics (
    id INTEGER PRIMARY KEY,
    cpu_percent REAL,
    ram_percent REAL,
    disk_percent REAL,
    temperature REAL,
    network_rx_bytes INTEGER,
    network_tx_bytes INTEGER,
    network_rx_packets INTEGER,
    network_tx_packets INTEGER,
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Note** : Pas de `TimestampMixin` - utilise `recorded_at` directement.

#### `alerts` - Alertes Suricata
```sql
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY,
    signature_id INTEGER,
    signature TEXT,
    severity INTEGER,
    src_ip TEXT,
    dest_ip TEXT,
    src_port INTEGER,
    dest_port INTEGER,
    protocol TEXT,
    timestamp DATETIME,
    payload TEXT,
    created_at DATETIME,
    updated_at DATETIME
);
```

### 3. Historique et Logs

#### `deployment_history` - Historique des Déploiements
```sql
CREATE TABLE deployment_history (
    id INTEGER PRIMARY KEY,
    deployment_type TEXT DEFAULT 'initial' 
        CHECK(deployment_type IN ('initial', 'update', 'rollback')),
    component TEXT DEFAULT 'all'
        CHECK(component IN ('dashboard', 'suricata', 'vector', 'elasticsearch', 
                           'tailscale', 'opensearch', 'all')),
    status TEXT DEFAULT 'in_progress'
        CHECK(status IN ('success', 'failed', 'in_progress')),
    error_message TEXT,
    error_diagnosis TEXT,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    created_at DATETIME,
    updated_at DATETIME
);
```

#### `error_logs` - Logs d'Erreurs
```sql
CREATE TABLE error_logs (
    id INTEGER PRIMARY KEY,
    component TEXT,
    error_type TEXT,
    error_message TEXT,
    traceback TEXT,
    diagnosis TEXT,
    resolved BOOLEAN DEFAULT 0,
    resolved_at DATETIME,
    created_at DATETIME,
    updated_at DATETIME
);
```

### 4. Données Externes

#### `tailscale_nodes` - Nœuds Tailscale
```sql
CREATE TABLE tailscale_nodes (
    id INTEGER PRIMARY KEY,
    node_id TEXT UNIQUE,
    hostname TEXT,
    ip TEXT,
    status TEXT,
    last_seen DATETIME,
    tags JSON DEFAULT '[]',
    latency_ms REAL,
    created_at DATETIME,
    updated_at DATETIME
);
```

#### `elasticsearch_indices` - Indices Elasticsearch/OpenSearch
```sql
CREATE TABLE elasticsearch_indices (
    id INTEGER PRIMARY KEY,
    index_name TEXT UNIQUE,
    size_bytes INTEGER,
    document_count INTEGER,
    creation_date DATETIME,
    created_at DATETIME,
    updated_at DATETIME
);
```

#### `elasticsearch_index_patterns` - Patterns d'Index
```sql
CREATE TABLE elasticsearch_index_patterns (
    id INTEGER PRIMARY KEY,
    pattern_name TEXT UNIQUE,
    pattern TEXT,
    time_field TEXT DEFAULT '@timestamp',
    created_at DATETIME,
    updated_at DATETIME
);
```

#### `elasticsearch_dashboards` - Dashboards
```sql
CREATE TABLE elasticsearch_dashboards (
    id INTEGER PRIMARY KEY,
    dashboard_name TEXT UNIQUE,
    dashboard_id TEXT UNIQUE,
    description TEXT,
    created_at DATETIME,
    updated_at DATETIME
);
```

## Pattern Singleton

La plupart des tables de configuration utilisent le pattern **singleton** :

```python
from ids.storage import crud, models, database

session = database.SessionLocal()
# Récupère l'unique instance ou en crée une si elle n'existe pas
secrets = crud.get_or_create_singleton(session, models.Secrets)
aws_config = crud.get_or_create_singleton(session, models.AwsConfig)
```

**Avantages** :
- Une seule source de vérité pour la configuration
- Pas de gestion de multiples instances
- Facile à mettre à jour

## Relations

**Pas de relations explicites (Foreign Keys)** - Architecture simple avec :
- Tables de configuration indépendantes (singleton)
- Tables de télémétrie avec données temporelles
- Pas de jointures complexes nécessaires

## Utilisation avec SecretManager

Le `SecretManager` utilise la table `secrets` :

```python
from ids.infrastructure import secret_manager

# Définir un secret
secret_manager.set_secret("aws_access_key_id", "AKIA...")

# Récupérer un secret
key = secret_manager.get_secret("aws_access_key_id")

# Plus besoin de variables d'environnement ou secret.json !
```

## Initialisation

```python
from ids.storage import database

# Créer les tables si elles n'existent pas
database.init_db()
```

La base de données est créée automatiquement dans `data/ids_dashboard.db`.

## Migration depuis config.yaml et secret.json

Les données peuvent être migrées depuis les fichiers de configuration :

```python
from ids.infrastructure import secret_manager
from ids.storage import crud, models, database
from ids.config.loader import ConfigManager

# Charger depuis secret.json
secret_manager.load_secrets_from_file(Path("secret.json"))

# Charger depuis config.yaml
config = ConfigManager("config.yaml")
session = database.SessionLocal()
aws_cfg = crud.get_or_create_singleton(session, models.AwsConfig)
aws_cfg.region = config.obtenir("aws.region")
aws_cfg.domain_name = config.obtenir("aws.domain_name")
session.commit()
```

## Schéma Visuel

```
┌─────────────────────────────────────────────────────────┐
│                    BASE DE DONNÉES                      │
│              SQLite (ids_dashboard.db)                  │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                     │
        ▼                   ▼                     ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ CONFIGURATION│   │   SECRETS     │   │  TÉLÉMÉTRIE  │
│  (Singleton) │   │  (Singleton)  │   │  (Time-Series)│
├──────────────┤   ├──────────────┤   ├──────────────┤
│ aws_config   │   │ secrets      │   │ system_metrics│
│ raspberry_pi │   │              │   │ alerts       │
│ suricata     │   │              │   │ services_status│
│ vector       │   │              │   │              │
│ redis        │   │              │   │              │
│ prometheus   │   │              │   │              │
│ grafana      │   │              │   │              │
│ docker       │   │              │   │              │
│ tailscale    │   │              │   │              │
│ fastapi      │   │              │   │              │
│ resource_ctrl│   │              │   │              │
│ connectivity │   │              │   │              │
└──────────────┘   └──────────────┘   └──────────────┘
        │                   │                     │
        └───────────────────┼───────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                     │
        ▼                   ▼                     ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   HISTORIQUE │   │   EXTERNES   │   │   MIXIN      │
├──────────────┤   ├──────────────┤   ├──────────────┤
│deployment_   │   │tailscale_    │   │TimestampMixin│
│  history     │   │  nodes       │   │  (created_at,│
│error_logs    │   │elasticsearch_│   │   updated_at)│
│              │   │  indices     │   │              │
│              │   │elasticsearch_│   │              │
│              │   │  patterns    │   │              │
│              │   │elasticsearch_│   │              │
│              │   │  dashboards │   │              │
└──────────────┘   └──────────────┘   └──────────────┘
```

## Accès aux Données

### Via CRUD Helpers

```python
from ids.storage import crud, models, database

session = database.SessionLocal()

# Récupérer ou créer un singleton
secrets = crud.get_or_create_singleton(session, models.Secrets)
secrets.aws_access_key_id = "AKIA..."
session.commit()

# Mettre à jour un modèle
crud.update_model(secrets, {"aws_secret_access_key": "xxx"})
session.commit()
```

### Via SecretManager

```python
from ids.infrastructure import secret_manager

# Plus simple et recommandé pour les secrets
secret_manager.set_secret("aws_access_key_id", "AKIA...")
key = secret_manager.get_secret("aws_access_key_id")
```

## Sécurité

⚠️ **IMPORTANT** : Les secrets sont stockés en **texte clair** dans SQLite.

**Recommandations pour la production** :
1. **Chiffrement au niveau colonne** : Chiffrer les colonnes sensibles
2. **Gestionnaire de secrets externe** : AWS Secrets Manager, HashiCorp Vault
3. **Permissions fichier** : `chmod 600 data/ids_dashboard.db`
4. **Chiffrement SQLite** : Utiliser SQLCipher

## Performance

- **SQLite** convient pour un dashboard avec peu de concurrence
- Les tables de télémétrie (`system_metrics`, `alerts`) peuvent grossir rapidement
- **Recommandation** : Implémenter une rotation/archivage des données anciennes
