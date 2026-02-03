
# IDS2 — SOC IDS sur Raspberry Pi 5

Ce projet implémente un **pipeline SOC IDS complet**, robuste et automatisé, basé sur **Suricata**, **Vector**, **Redis** et **AWS OpenSearch**, déployé sur un **Raspberry Pi 5 (8 GB RAM)**.
L’architecture est conçue pour fonctionner **24/7**, sous contraintes de ressources, avec **parallélisme contrôlé**, **backpressure**, **observabilité complète** et **pilotage local via interface Web**.

---

## Table des matières

1. Objectifs du projet
2. Périmètre et principes généraux
3. Plateforme matérielle et contraintes
4. Vue d’ensemble de l’architecture
5. Flux de données (pipeline SOC)
6. Rôle des composants
7. Organisation des services (systemd & Docker)
8. Gestion des ressources (CPU / RAM / disque)
9. Gestion des logs et de la mémoire
10. Parallélisme et multi-process
11. Sécurité réseau
12. Observabilité et pilotage Web
13. Automatisation et déploiement
14. Exploitation et cycle de vie
15. Résumé final
16. **[Documentation UML / Architecture](docs/uml/README.md)** 🎨

---

## 1. Objectifs du projet

Les objectifs principaux sont :

* Déployer un **IDS passif** basé sur Suricata via **port mirroring**
* Centraliser les événements de sécurité dans **AWS OpenSearch**
* Garantir la **stabilité du système** sous forte charge
* Ne **jamais dépasser 70 % de CPU et de RAM**
* Fournir une **observabilité complète** (logs, métriques, dashboards)
* Permettre un **pilotage local sans SSH** (interface Web)
* Automatiser **100 % du déploiement** après un reset usine du Pi

---

## 2. Périmètre et principes généraux

### Ce que fait le projet

* Capture passive du trafic réseau
* Détection IDS (alertes, anomalies)
* Transformation des événements en format ECS
* Bufferisation intelligente en cas de surcharge
* Ingestion sécurisée vers OpenSearch
* Supervision continue des ressources
* Administration locale centralisée

### Ce que le projet ne fait pas

* Pas d’IPS (aucun blocage réseau)
* Pas d’inspection de paquets en Python
* Pas de stockage long terme local
* Pas d’exposition directe à Internet

---

## 3. Plateforme matérielle et contraintes

### Raspberry Pi cible

| Élément          | Valeur                       |
| ---------------- | ---------------------------- |
| Modèle           | Raspberry Pi 5               |
| CPU              | 4 × Cortex-A76               |
| RAM              | 8 GB                         |
| OS               | Debian GNU/Linux 13 (Trixie) |
| IP               | **192.168.178.66**           |
| Interface réseau | **eth0 uniquement**          |
| Swap             | 2 GB                         |
| Stockage         | microSD 119 GB               |

### Contraintes strictes

* CPU total ≤ **70 %**
* RAM totale ≤ **70 %**
* Fonctionnement continu (24/7)
* Résistance aux pics de trafic (burst IDS)
* Aucun appel bloquant dans la boucle critique

---

## 4. Vue d’ensemble de l’architecture

### Architecture logique

```
Trafic réseau (mirroring)
        ↓
     Suricata
        ↓
    eve.json (RAM)
        ↓
      Vector
        ↓
      Redis (buffer)
        ↓
 AWS OpenSearch
        ↓
 Dashboards & Alertes
```

### Architecture physique

* **Raspberry Pi** : capture, transformation, orchestration
* **AWS** : indexation, recherche, visualisation distante

---

## 5. Flux de données (pipeline SOC)

1. Le trafic réseau est dupliqué via **port mirroring**
2. Suricata capture les paquets sur `eth0`
3. Les événements sont écrits dans `eve.json`
4. Vector lit les événements en temps réel
5. Les événements sont mappés au format **ECS**
6. Redis absorbe les pics si OpenSearch ralentit
7. Les données sont envoyées en **bulk HTTPS**
8. Les dashboards affichent les alertes et métriques

---

## 6. Rôle des composants

### Suricata

* IDS haute performance (C / kernel)
* Capture passive uniquement
* Fonctionne **hors Docker**
* Écrit exclusivement en local
* Géré comme un service `systemd`

### Vector

* Collecte et transformation des logs
* Mapping ECS natif
* Batching, retry, backoff
* Fonctionne en **Docker**

### Redis

* Buffer de sécurité
* Backpressure
* Évite la perte de logs

### AWS OpenSearch

* Indexation et recherche
* Stockage long terme
* Dashboards et alertes

### Agent SOC Python

* Orchestrateur central
* Multi-process
* Supervision CPU/RAM
* Pilotage systemd & Docker
* Backend de la Web UI

---

## 7. Organisation des services

### systemd (host)

* `network-eth0-only.service` : force `eth0` uniquement
* `suricata.service` : capture IDS
* `ids2-agent.service` : orchestration SOC

### Docker

* Vector
* Redis
* Prometheus
* Grafana
* FastAPI (control plane)
* cAdvisor
* Node Exporter

Chaque service est **isolé**, supervisé et redémarré automatiquement.

---

## 8. Gestion des ressources (CPU / RAM)

### Répartition CPU

* Suricata : ~3 cœurs
* Vector : ~1 cœur
* Redis : ~0.5 cœur
* Prometheus : ~0.2 cœur
* Grafana : ~0.2 cœur
* FastAPI : ~0.5 cœur
* cAdvisor : ~0.1 cœur
* Node Exporter : ~0.1 cœur

### Répartition RAM

* Suricata : ~4 GB
* Vector : ~1 GB
* Redis : ~512 MB
* Prometheus : ~256 MB
* Grafana : ~256 MB
* FastAPI : ~256 MB
* cAdvisor : ~64 MB
* Node Exporter : ~64 MB
* Libre : >1 GB

### Mécanismes de contrôle

* Limites systemd (`CPUQuota`, `MemoryMax`)
* Limites Docker (`cpus`, `mem_limit`)
* Throttling dynamique par l’agent
* Backpressure Redis
* Batching Vector

---

## 9. Gestion des logs et de la mémoire

### Logs Suricata

* Stockés en **RAM disk**
* Taille maximale strictement bornée
* Rotation agressive
* Aucun historique local conservé

### Mémoire

* Aucun cache applicatif long terme
* Garbage collection Python forcée
* Nettoyage périodique du cache kernel
* Swappiness faible

Objectif : **zéro fuite mémoire**, même après plusieurs semaines.

---

## 10. Parallélisme et multi-process

### Agent SOC

L’agent est découpé en **processus indépendants** :

* Superviseur
* Contrôle ressources
* Tests réseau (async)
* Monitoring / métriques
* Vérification ingestion (optionnel)

### Bénéfices

* Isolation mémoire
* Résilience
* Exploitation optimale des 4 cœurs
* Pas de contention GIL critique

---

## 11. Sécurité réseau

* Une seule interface active : **eth0**
* Mode promiscuous activé
* Firewall sortant strict (HTTPS + DNS)
* Aucune exposition Internet
* Administration uniquement LAN

---

## 12. Observabilité et pilotage Web

### Observabilité

* Prometheus : métriques
* Grafana : dashboards SOC
* OpenSearch : analyse sécurité

### Web Control Plane

* Endpoint HTTP `/status` pour le statut du pipeline
* Endpoint `/health` pour health check
* Visualisation état pipeline (composants, métriques)
* CPU / RAM / débit
* Modification des paramètres (via API)
* Redémarrage des services (via API)
* Gestion Docker

Aucun accès SSH requis pour l'exploitation courante.

---

## 13. Automatisation et déploiement

* Le script `deploy/push_to_pi.sh` ou `python -m ids.deploy.pi_uploader` permet le déploiement complet
* Vérifie la connectivité (SSH, Docker, AWS)
* Build et push de l'image Docker vers le Pi
* Synchronise les fichiers nécessaires (config, secrets, code)
* Les credentials AWS sont fournis via `secret.json` (copier `secret.json.example`)
* Génère `docker/.env` pour injecter AWS/endpoint dans Docker Compose
* Active les services systemd et Docker Compose
* Idempotent et rejouable
* Fonctionne après reset usine du Pi
* Configure réseau, services, Docker, agent
* Démarrage automatique au boot

---

## 14. Exploitation et cycle de vie

* Démarrage automatique
* Supervision continue
* Redémarrage en cas de crash
* Mise à jour contrôlée
* Reset complet possible
* Extensible (forensic, IPS, ML…)

---

## 15. Résumé final

✔ IDS passif haute performance
✔ Architecture SOC moderne
✔ Pipeline résilient et observable
✔ Ressources strictement contrôlées
✔ Automatisation complète
✔ Pilotage Web local
✔ Adapté Raspberry Pi 5
✔ Prêt production 24/7

---

## 16. GitHub Actions depuis Codespaces

Les **Codespaces user secrets** ne sont pas disponibles automatiquement dans
GitHub Actions. Pour lancer le workflow CI/CD depuis un Codespace :

1. Copiez `scripts/actions_secrets.map.example` en `scripts/actions_secrets.map`
   et ajustez les noms des variables source.
   * OAuth Tailscale : `TAILSCALE_OAUTH_CLIENT_ID`,
     `TAILSCALE_OAUTH_CLIENT_SECRET`.
   * API Tailscale (check connectivité) : `TAILSCALE_TAILNET`,
     `TAILSCALE_API_KEY`.
   * AWS (check connectivité) : `AWS_ACCESS_KEY_ID`,
     `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `AWS_SESSION_TOKEN` (optionnel).
2. Synchronisez vos secrets vers le dépôt :
   `scripts/gh_actions_sync_secrets.sh --repo OWNER/REPO`
   * Le script utilise `GITAPI` comme `GH_TOKEN` si présent.
3. Déclenchez le workflow :
   `scripts/gh_actions_run.sh --ref main`
   (ou `gh workflow run ci-cd.yml --ref main`).

Prérequis : le CLI `gh` doit être installé et votre token GitHub doit avoir
les droits nécessaires (ex: `repo` + `workflow` pour un dépôt privé).
