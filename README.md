# Architecture du pipeline SOC IDS

Ce document décrit l’architecture cible du pipeline SOC pour un IDS Suricata déployé sur **Raspberry Pi 5 (8 GB RAM)**, avec ingestion vers **AWS OpenSearch**, orchestration Python, parallélisme contrôlé et déploiement Docker.

---

## 0) Contexte matériel & contraintes

### Raspberry Pi cible

| Élément          | Valeur                       |
| ---------------- | ---------------------------- |
| Modèle           | Raspberry Pi 5               |
| RAM              | 8 GB                         |
| CPU              | 4 × Cortex-A76               |
| OS               | Debian GNU/Linux 13 (Trixie) |
| IP fixe          | **192.168.178.66**           |
| Interface réseau | **eth0 uniquement**          |
| Swap             | 2 GB                         |
| Stockage         | microSD 119 GB               |

### Contraintes clés

* **CPU total utilisé ≤ 70 %**
* **RAM totale utilisée ≤ 70 %**
* Tolérance aux pics de trafic (burst IDS)
* Aucun blocage réseau ou CPU lors des tests AWS
* Pipeline résilient (buffer + backpressure)

---

## 1) Bibliothèques nécessaires

### Python (`requirements.txt`)

| Bibliothèque      | Rôle                                    |
| ----------------- | --------------------------------------- |
| boto3             | SDK AWS (création / gestion OpenSearch) |
| opensearch-py     | Client OpenSearch (bulk, health checks) |
| uvloop            | Boucle asyncio ultra-performante        |
| asyncio           | Parallélisme I/O                        |
| orjson            | Sérialisation JSON rapide               |
| msgpack-python    | Format binaire rapide (interne)         |
| aioredis          | Buffer Redis asynchrone                 |
| PyYAML            | Parsing `config.yaml`                   |
| watchdog          | Suivi temps réel de `eve.json`          |
| requests          | HTTP simple                             |
| prometheus-client | Export métriques                        |
| GitPython         | Commit / push sur branche `dev`         |
| pytest            | Tests                                   |

---

## 2) Stratégie globale

Le projet repose sur une **stratégie “pipeline orienté flux”**, découplée, asynchrone et résiliente.

### Principes clés

* **Découplage** : Suricata ≠ Vector ≠ OpenSearch
* **Backpressure** : Redis absorbe les pics
* **Async first** : aucun appel réseau bloquant
* **Configuration unique** : `config.yaml`
* **Automatisation totale** : zéro configuration manuelle
* **Observabilité native** : métriques partout

---

## 3) Qu’est-ce que l’AWS SDK (boto3) ?

`boto3` est le **SDK officiel AWS pour Python**.

Il permet :

* Authentification via **SigV4**
* Appels API sécurisés
* Création / description de ressources AWS
* Polling d’état non bloquant

### Utilisation dans ce projet

* Création ou récupération du **OpenSearch Domain**
* Attente de l’état `ACTIVE`
* Récupération de l’endpoint
* Application d’index templates
* Tests de connectivité

---

## 4) Qu’est-ce que le pipeline SOC ?

Un pipeline SOC est une **chaîne continue de traitement de logs sécurité**.

### Chaîne logique

1. Capture réseau (Suricata)
2. Écriture JSON (`eve.json`)
3. Parsing / mapping ECS (Vector)
4. Bufferisation (Redis)
5. Ingestion bulk (OpenSearch)
6. Visualisation / alertes
7. Monitoring système & pipeline

### Schéma simplifié

```
Suricata → Vector → Redis → OpenSearch
              ↓
         Prometheus → Grafana
```

---

## 5) Structures de données

### 5.1 Suricata JSON (eve.json)

```json
{
  "timestamp": "2026-02-01T02:10:00.123Z",
  "event_type": "alert",
  "src_ip": "192.168.178.5",
  "dest_ip": "10.0.0.10",
  "alert": {
    "signature": "ET SCAN ...",
    "severity": 2
  }
}
```

---

### 5.2 ECS (après Vector)

```json
{
  "@timestamp": "2026-02-01T02:10:00.123Z",
  "event": {
    "kind": "alert",
    "category": "network"
  },
  "source": {
    "ip": "192.168.178.5"
  },
  "destination": {
    "ip": "10.0.0.10"
  },
  "suricata": {
    "signature": "ET SCAN ...",
    "severity": 2
  }
}
```

---

### 5.3 Bulk OpenSearch (NDJSON)

```
{ "index": { "_index": "suricata-2026.02.01" } }
{ "doc ECS" }
```

---

## 6) Phases du système

### Phase A — Initialisation Raspberry Pi

* Désactiver toutes les interfaces sauf `eth0`
* Configurer firewall minimal
* Créer RAM disk pour logs
* Installer Docker & Python

---

### Phase B — Provisioning AWS

* Charger `config.yaml`
* Vérifier credentials
* Créer ou détecter domaine
* Attendre `ACTIVE`
* Sauvegarder endpoint

---

### Phase C — Tests réseau (asynchrones)

Exécutés **en parallèle** :

* DNS
* TLS
* Bulk

---

### Phase D — Génération de configurations

* `suricata.yaml`
* `vector.toml`
* `docker-compose.yml`
* `prometheus.yml`
* Dashboards Grafana

---

### Phase E — Déploiement Docker

* Redis
* Vector
* Prometheus
* Grafana

---

### Phase F — Ingestion & monitoring

* Tail `eve.json`
* Vector → Redis → OpenSearch
* Export métriques
* Alerting

---

### Phase G — Git (branche dev)

* Vérification branche `dev`
* Commit automatique
* Push sur `dev`

---

## 7) Conteneurs Docker

| Conteneur     | Rôle                                |
| ------------- | ----------------------------------- |
| Suricata      | Capture réseau + détection IDS      |
| Redis         | Buffer backpressure                 |
| Vector        | Parsing + ingestion                 |
| Prometheus    | Collecte métriques                  |
| Grafana       | Dashboards                          |
| cAdvisor      | Surveillance des conteneurs Docker  |
| Node Exporter | Surveillance des ressources hôtes   |

---

## 8) Parallélisme & multithreading

### 8.1 Parallélisme Python (I/O)

Utilisé pour :

* DNS
* TLS
* Tests bulk
* Monitoring

```python
await asyncio.gather(
  test_dns(),
  test_tls(),
  test_bulk()
)
```

### 8.2 Vector (natif)

Vector est écrit en **Rust**, multi-thread nativement :

* Lecture fichiers
* Parsing ECS
* Batching
* Retry/backoff

---

## 9) Gestion CPU & RAM (< 70 %)

### Répartition CPU

| Composant     | CPU     |
| ------------- | ------- |
| Suricata      | 3 cœurs |
| Vector        | 1 cœur  |
| Redis         | 0.5 cœur |
| Prometheus    | 0.2 cœur |
| Grafana       | 0.2 cœur |
| cAdvisor      | 0.1 cœur |
| Node Exporter | 0.1 cœur |

### Répartition RAM

| Composant     | RAM max |
| ------------- | ------- |
| Suricata      | ~4 GB   |
| Vector        | ~1 GB   |
| Redis         | ~512 MB |
| Prometheus    | ~256 MB |
| Grafana       | ~256 MB |
| cAdvisor      | ~64 MB  |
| Node Exporter | ~64 MB  |
| Libre         | >1 GB   |

### Mécanismes de contrôle

* Limites Docker (`mem_limit`, `cpus`)
* Batching Vector
* Chunking async Python
* Garbage collection Python forcée
* Rotation logs RAM disk

---

## 10) Réseau & sécurité

### Interface

* **eth0 uniquement**
* IP : **192.168.178.66**

```bash
ip link set wlan0 down
ip link set usb0 down
```

### Firewall minimal

```bash
iptables -A OUTPUT -o eth0 -p tcp --dport 443 -j ACCEPT
iptables -A OUTPUT -o eth0 -p udp --dport 53 -j ACCEPT
iptables -P OUTPUT DROP
iptables -P INPUT DROP
```

---

## 11) Agent SOC

Le projet inclut un **agent SOC Python** qui :

* Orchestre toutes les phases
* Surveille l’état du pipeline
* Expose métriques Prometheus
* Gère les retries
* Contrôle l’utilisation CPU/RAM
* Peut être lancé comme **service systemd**

👉 L’agent est le **cerveau du système**.

---

## 12) Amazon Q dans VS Code

### Prérequis

* Extension **AWS Toolkit / Amazon Q** installée
* Profil AWS déjà configuré : **`moi33`**
* Variables AWS déjà présentes

### Configuration

Dans VS Code :

1. Ouvrir **AWS Toolkit**
2. Sélectionner le profil **`moi33`**
3. Vérifier la région (`eu-central-1`)

### Utilisation avec ce projet

Amazon Q peut :

* Expliquer le code
* Générer des tests
* Vérifier la config AWS
* Aider à déboguer Vector / Suricata

Aucune configuration supplémentaire requise.

---

## 13) Résumé final

✔ Architecture robuste
✔ Async & multithread contrôlé
✔ Limites CPU/RAM respectées
✔ Observabilité complète
✔ Sécurité réseau stricte
✔ Déploiement reproductible
✔ Agent SOC central
✔ Compatible Amazon Q / VS Code
Parfait — j’ai **adapté et enrichi ton README** en intégrant **la Web App de contrôle (Control Plane)**, **la visualisation**, **le redémarrage des services**, **la modification des paramètres**, tout en restant **cohérent avec toute la discussion** (systemd, Docker, agent, Pi 5).

Tu peux **copier-coller tel quel** ce README et remplacer l’actuel.

---

# Architecture du pipeline SOC IDS

Ce document décrit l’architecture cible du pipeline SOC pour un IDS Suricata déployé sur **Raspberry Pi 5 (8 GB RAM)**, avec ingestion vers **AWS OpenSearch**, orchestration Python **multi-process**, parallélisme contrôlé, **interface Web de pilotage**, et déploiement Docker.

---

## 0) Contexte matériel & contraintes

### Raspberry Pi cible

| Élément          | Valeur                       |
| ---------------- | ---------------------------- |
| Modèle           | Raspberry Pi 5               |
| RAM              | 8 GB                         |
| CPU              | 4 × Cortex-A76               |
| OS               | Debian GNU/Linux 13 (Trixie) |
| IP fixe          | **192.168.178.66**           |
| Interface réseau | **eth0 uniquement**          |
| Swap             | 2 GB                         |
| Stockage         | microSD 119 GB               |

### Contraintes clés

* **CPU total utilisé ≤ 70 %**
* **RAM totale utilisée ≤ 70 %**
* Tolérance aux pics de trafic (burst IDS)
* Aucun appel réseau bloquant dans la boucle critique
* Pipeline résilient (buffer + backpressure)
* Administration locale via Web UI (LAN uniquement)

---

## 1) Bibliothèques nécessaires

### Python (`requirements.txt`)

| Bibliothèque      | Rôle                                    |
| ----------------- | --------------------------------------- |
| boto3             | SDK AWS (création / gestion OpenSearch) |
| opensearch-py     | Client OpenSearch (bulk, health checks) |
| uvloop            | Boucle asyncio ultra-performante        |
| asyncio           | Parallélisme I/O                        |
| orjson            | Sérialisation JSON rapide               |
| msgpack-python    | Format binaire interne                  |
| aioredis          | Buffer Redis asynchrone                 |
| PyYAML            | Parsing `config.yaml`                   |
| watchdog          | Suivi temps réel de `eve.json`          |
| requests          | HTTP                                    |
| prometheus-client | Export métriques                        |
| psutil            | CPU / RAM                               |
| fastapi           | Web Control Plane                       |
| uvicorn           | Serveur API                             |
| docker            | Pilotage Docker                         |
| GitPython         | Commit / push sur branche `dev`         |
| pytest            | Tests                                   |

---

## 2) Stratégie globale

Le projet repose sur une **stratégie pipeline orientée flux**, **pilotée par un agent central**, observable et contrôlable via **interface Web locale**.

### Principes clés

* **Découplage fort** : Suricata ≠ Vector ≠ OpenSearch
* **Backpressure** : Redis absorbe les pics
* **Async + multi-process** : séparation contrôle / ingestion / monitoring
* **Configuration unique** : `config.yaml`
* **Contrôle dynamique** : paramètres ajustables sans reboot
* **Observabilité native** : métriques + dashboards
* **Administration Web locale** : actions sans SSH

---

## 3) Rôle de l’AWS SDK (boto3)

`boto3` est le **SDK officiel AWS pour Python**.

Utilisé pour :

* Créer / décrire un domaine OpenSearch
* Poller l’état (`CREATING → ACTIVE`)
* Récupérer l’endpoint
* Appliquer templates et policies
* Tester la connectivité (SigV4)

---

## 4) Pipeline SOC (concept)

Chaîne de traitement :

1. Capture réseau (port mirroring → eth0)
2. Détection IDS (Suricata)
3. Logs JSON (`eve.json`)
4. Parsing & mapping ECS (Vector)
5. Buffer Redis (si pression)
6. Ingestion bulk (OpenSearch)
7. Visualisation & alertes
8. Pilotage Web & monitoring

```
Suricata → Vector → Redis → OpenSearch
              ↓
        Prometheus → Grafana
              ↓
          FastAPI UI
```

---

## 5) Structures de données

### 5.1 Suricata JSON (`eve.json`)

```json
{
  "timestamp": "2026-02-01T02:10:00.123Z",
  "event_type": "alert",
  "src_ip": "192.168.178.5",
  "dest_ip": "10.0.0.10",
  "alert": {
    "signature": "ET SCAN ...",
    "severity": 2
  }
}
```

### 5.2 ECS (après Vector)

```json
{
  "@timestamp": "2026-02-01T02:10:00.123Z",
  "event": { "kind": "alert", "category": "network" },
  "source": { "ip": "192.168.178.5" },
  "destination": { "ip": "10.0.0.10" },
  "suricata": { "signature": "ET SCAN ...", "severity": 2 }
}
```

### 5.3 Bulk OpenSearch (NDJSON)

```
{ "index": { "_index": "suricata-2026.02.01" } }
{ ... ECS document ... }
```

---

## 6) Phases du système

### Phase A — Initialisation Pi

* Désactivation interfaces hors `eth0`
* Mode promiscuous
* Firewall minimal
* RAM disk logs
* Installation Docker + Python

### Phase B — Provisioning AWS

* Lecture `config.yaml`
* Vérification credentials
* Création ou récupération domaine
* Attente `ACTIVE`
* Sauvegarde endpoint

### Phase C — Tests réseau (async)

* DNS
* TLS
* Bulk OpenSearch
  → **exécutés en parallèle**

### Phase D — Génération des configurations

* `suricata.yaml`
* `vector.toml`
* `docker-compose.yml`
* `prometheus.yml`
* Dashboards Grafana

### Phase E — Déploiement Docker

* Redis
* Vector
* Prometheus
* Grafana
* FastAPI Control Plane

### Phase F — Ingestion & Monitoring

* Tail `eve.json`
* Vector → Redis → OpenSearch
* Métriques Prometheus
* Dashboards Grafana

### Phase G — Pilotage & Git

* Interface Web pour actions
* Commit auto sur branche `dev`
* Push contrôlé

---

## 7) Conteneurs Docker

| Conteneur     | Rôle                    |
| ------------- | ----------------------- |
| Redis         | Buffer / backpressure   |
| Vector        | Parsing ECS + ingestion |
| Prometheus    | Collecte métriques      |
| Grafana       | Visualisation           |
| FastAPI       | Web Control Plane       |
| cAdvisor      | Métriques Docker        |
| Node Exporter | Métriques hôte          |

⚠️ **Suricata n’est PAS dockerisé** (capture réseau).

---

## 8) Parallélisme & multi-process

### Python (agent SOC)

* **Process Supervisor**
* **Process contrôle ressources**
* **Process tests réseau (async)**
* **Process métriques**
* (optionnel) **Process vérification ingestion**

### Async I/O

```python
await asyncio.gather(
  test_dns(),
  test_tls(),
  test_bulk()
)
```

### Vector

* Multithread natif (Rust)
* Batching, retry, backoff intégrés

---

## 9) Gestion CPU & RAM (< 70 %)

### Répartition CPU

| Composant | CPU     |
| --------- | ------- |
| Suricata  | 3 cœurs |
| Vector    | 1 cœur  |
| Autres    | limité  |

### Répartition RAM

| Composant    | RAM max |
| ------------ | ------- |
| Suricata     | ~4 GB   |
| Vector       | ~1 GB   |
| Redis        | ~512 MB |
| Stack Docker | ~1 GB   |
| Libre        | >1 GB   |

### Mécanismes

* `CPUQuota` / `MemoryMax` systemd
* Limites Docker (`cpus`, `mem_limit`)
* Throttling dynamique agent
* Chunking async
* GC Python sous pression
* Rotation logs RAM disk

---

## 10) Réseau & sécurité

### Interface

* **eth0 uniquement**
* IP : **192.168.178.66**

```bash
ip link set wlan0 down
ip link set usb0 down
```

### Firewall minimal

```bash
iptables -A OUTPUT -o eth0 -p tcp --dport 443 -j ACCEPT
iptables -A OUTPUT -o eth0 -p udp --dport 53 -j ACCEPT
iptables -P OUTPUT DROP
iptables -P INPUT DROP
```

---

## 11) Agent SOC (cerveau)

L’agent SOC Python :

* Orchestre toutes les phases
* Supervise les services
* Surveille CPU / RAM
* Applique throttling
* Expose métriques Prometheus
* Pilote Docker et systemd
* Sert de backend à la Web UI

---

## 12) Web Control Plane (UI)

### Composants

* **FastAPI** (backend API)
* **Swagger UI** (`/docs`)
* **Grafana** (graphiques)
* **Prometheus** (données)

### Fonctions Web

* Visualiser l’état du pipeline
* Voir CPU / RAM / débit
* Modifier `config.yaml`
* Ajuster batch Vector
* Redémarrer :

  * Suricata
  * Agent
  * Docker stack
* Voir l’état systemd / Docker

Accès local :

```
http://192.168.178.66:8000/docs
http://192.168.178.66:3000
```

---

## 13) Amazon Q dans VS Code

### Prérequis

* Extension AWS Toolkit / Amazon Q
* Profil AWS : **`moi33`**
* Région : `eu-central-1`

### Usage

* Analyse du code
* Debug config AWS
* Génération de tests
* Aide Vector / Suricata

---

## 14) Résumé final

✔ IDS passif haute performance
✔ Pipeline résilient & observable
✔ Multi-process & async maîtrisés
✔ Limites CPU/RAM garanties
✔ Pilotage Web local
✔ Déploiement reproductible
✔ Compatible Amazon Q / VS Code
✔ Adapté production 24/7

---

Si tu veux la suite, je peux maintenant :

* générer **l’API FastAPI complète**
* générer **les dashboards Grafana**
* intégrer **le contrôle Web directement dans l’agent**
* fournir **les règles RBAC**

Dis-moi 🚀
