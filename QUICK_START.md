# 🚀 IDS2 - Quick Start

## Installation Rapide

```bash
cd /home/tor/Downloads/ids2

# Démarrer la stack ELK
docker compose up -d

# Attendre 30 secondes pour l'initialisation
sleep 30

# Vérifier que tout tourne
docker ps
```

## Accès

- **Elasticsearch**: http://localhost:9200
- **Kibana**: http://localhost:5601
- **Index**: `alexis` (pré-configuré avec 12 champs)

## Tester l'index

```bash
# Voir l'index
curl http://localhost:9200/_cat/indices?v

# Ajouter un document
curl -X POST "http://localhost:9200/alexis/_doc" -H 'Content-Type: application/json' -d'
{
  "@timestamp": "2026-02-06T22:00:00Z",
  "message": "Test IDS alert",
  "severity": "high",
  "source_ip": "192.168.1.100",
  "dest_ip": "10.0.0.1",
  "source_port": 54321,
  "dest_port": 80,
  "protocol": "TCP",
  "event_type": "alert",
  "signature": "Suspicious activity detected",
  "category": "network",
  "action": "blocked"
}'

# Rechercher
curl "http://localhost:9200/alexis/_search?pretty"
```

## Arrêter

```bash
docker compose down
```

## Réinitialiser

```bash
docker compose down
docker volume rm ids2_es_data ids2_kibana_data
docker compose up -d
```
