# Communication entre Services Docker

Ce document décrit comment les différents services Docker communiquent entre eux dans l'architecture IDS.

## Architecture Réseau

Tous les services Docker sont connectés au réseau `ids-network` (bridge network) défini dans `docker-compose.yml`.

```yaml
networks:
  ids-network:
    driver: bridge
```

## Services et leurs Communications

### 1. Vector → Redis

**Communication**: Vector écrit les données transformées dans Redis pour le buffering.

**Configuration**:
- Vector utilise la variable d'environnement `REDIS_URL` ou se connecte au service `redis` sur le port 6379
- Dans docker-compose, Vector a `depends_on: [redis]` pour s'assurer que Redis démarre en premier
- Communication via le réseau Docker interne: `redis:6379`

**Exemple de configuration Vector**:
```toml
[sinks.redis]
type = "redis"
inputs = ["transform"]
key = "suricata-events"
url = "redis://redis:6379"
```

### 2. Vector → OpenSearch (AWS)

**Communication**: Vector envoie les données finales vers OpenSearch sur AWS.

**Configuration**:
- Vector utilise les variables d'environnement:
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `AWS_REGION`
  - `OPENSEARCH_ENDPOINT`
- Communication HTTPS vers l'endpoint OpenSearch externe
- Les credentials sont injectés via les variables d'environnement du docker-compose

**Exemple de configuration Vector**:
```toml
[sinks.opensearch]
type = "aws_opensearch"
inputs = ["transform"]
endpoint = "${OPENSEARCH_ENDPOINT}"
region = "${AWS_REGION}"
```

### 3. Prometheus → Node Exporter & cAdvisor

**Communication**: Prometheus scrape les métriques depuis Node Exporter et cAdvisor.

**Configuration**:
- Prometheus a `depends_on: [node_exporter, cadvisor]`
- Prometheus se connecte aux endpoints HTTP des exporters:
  - `node_exporter:9100/metrics`
  - `cadvisor:8080/metrics`
- Communication via le réseau Docker interne

**Configuration Prometheus** (`prometheus.yml`):
```yaml
scrape_configs:
  - job_name: 'node_exporter'
    static_configs:
      - targets: ['node_exporter:9100']
  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']
```

### 4. Grafana → Prometheus

**Communication**: Grafana interroge Prometheus pour les données de monitoring.

**Configuration**:
- Grafana a `depends_on: [prometheus]`
- Grafana se connecte à Prometheus via: `prometheus:9090`
- Communication via le réseau Docker interne
- Configuration dans Grafana UI: Data Source → Prometheus → URL: `http://prometheus:9090`

### 5. FastAPI (ids-api) → Base de données & Services

**Communication**: L'API FastAPI peut accéder à la base de données et aux autres services.

**Configuration**:
- FastAPI a accès à la base de données SQLite via volume monté
- FastAPI peut interroger Redis, Prometheus, etc. via le réseau Docker
- Ports exposés: `8080:8080` pour l'accès externe

### 6. Vector → Suricata (Host)

**Communication**: Vector lit les logs Suricata depuis le disque RAM monté.

**Configuration**:
- Volume partagé: `/mnt/ram_logs:/mnt/ram_logs`
- Vector lit le fichier `/mnt/ram_logs/eve.json` généré par Suricata
- Suricata tourne sur le host (pas dans Docker) et écrit dans le volume monté
- Communication via système de fichiers partagé

## Variables d'Environnement pour Communication

Les services utilisent des variables d'environnement pour se connecter entre eux:

```bash
# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Prometheus
PROMETHEUS_URL=http://prometheus:9090

# OpenSearch
OPENSEARCH_ENDPOINT=https://search-xxx.es.amazonaws.com
AWS_REGION=eu-central-1

# Grafana
GRAFANA_URL=http://grafana:3000
```

## Dépendances de Démarrage

L'ordre de démarrage est géré par `depends_on` dans docker-compose.yml:

1. **ids-base** (image de base)
2. **ids-runtime** (dépend de ids-base)
3. **redis** (service indépendant)
4. **node_exporter** & **cadvisor** (services indépendants)
5. **prometheus** (dépend de node_exporter, cadvisor)
6. **grafana** (dépend de prometheus)
7. **vector** (dépend de redis)
8. **ids-api** (dépend de ids-base, ids-runtime)

## Health Checks

Pour s'assurer que les services sont prêts avant de démarrer les dépendances, on peut utiliser:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:9090/-/healthy"]
  interval: 10s
  timeout: 5s
  retries: 3
```

## Résolution DNS dans Docker

Docker fournit un DNS interne qui résout les noms de services:
- `redis` → IP du conteneur Redis
- `prometheus` → IP du conteneur Prometheus
- `grafana` → IP du conteneur Grafana
- etc.

C'est pourquoi on utilise `redis:6379` au lieu de `localhost:6379` dans les configurations.

## Isolation et Sécurité

- Tous les services sont sur le même réseau `ids-network` (bridge)
- Les ports ne sont exposés que si nécessaire (ex: Grafana 3000, Prometheus 9090)
- Les secrets sont passés via variables d'environnement (gérées par SecretManager)
- Pas de communication directe entre services non nécessaires

## Debugging Communication

Pour déboguer les communications:

```bash
# Vérifier les réseaux Docker
docker network ls
docker network inspect ids-network

# Vérifier les conteneurs sur le réseau
docker network inspect ids-network | grep Containers

# Tester la connectivité depuis un conteneur
docker exec -it vector ping redis
docker exec -it grafana curl http://prometheus:9090/-/healthy
```
