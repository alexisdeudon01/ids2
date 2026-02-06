# Changements Majeurs - Refactoring SSH + DB

## 🎯 Objectifs atteints

### 1. ✅ Clés SSH unifiées
- **Une seule clé** (`/home/tor/.ssh/pi_key`) pour toutes les connexions
- Upload automatique sur Pi ET EC2
- Plus de clés séparées EC2 (`ids2_ec2_key` supprimé)
- Vérification existence avant overwrite

### 2. ✅ Tout en SSH (plus de SSM AWS)
- Orchestrator utilise SSH pur
- Upload clés via SSH direct (pas SSM)
- Health check SSH toutes les 10s
- SSM gardé uniquement dans aws_deployer.py pour compatibilité

### 3. ✅ Base de données intégrée
**Nouvelle table `ec2_instances`:**
```sql
CREATE TABLE ec2_instances (
    instance_id TEXT UNIQUE,
    region TEXT,
    instance_type TEXT,
    public_ip TEXT,
    private_ip TEXT,
    state TEXT,
    elk_deployed INTEGER,
    created_at TEXT,
    updated_at TEXT
)
```

**Nouvelles méthodes DB:**
- `upsert_ec2_instance()` - Insert/update instance
- `get_ec2_instances()` - Liste toutes instances
- `delete_ec2_instance()` - Supprime instance
- `get_latest_deployment_config()` - Récupère dernière config

### 4. ✅ Workflow refondu (Ordre correct)
```
1. Connexion Pi
2. Deploy Suricata
3. Deploy & Test DB
4. Upload clé SSH sur Pi
5. Check DB instances existantes
6. Réconciliation AWS ↔ DB
7. Deploy EC2
8. Upload clé SSH sur EC2
9. Health monitor SSH (10s)
10. Config Elasticsearch
11. Update DB avec instance
12. Save deployment config
13. Install streamer
```

### 5. ✅ Health Monitor SSH
- Thread dédié
- Check toutes les 10 secondes
- Pi + EC2 simultanément
- Logs: `🔁 SSH Health (Pi) ✅ | (EC2) ✅`

## 📁 Fichiers modifiés

### `webbapp/db/database.py`
- ✅ Ajout table `ec2_instances`
- ✅ Ajout champ `ssh_key_path` dans `deployment_config`
- ✅ Nouvelles méthodes CRUD pour instances
- ✅ Méthode `get_latest_deployment_config()`

### `webbapp/ids/deploy/orchestrator.py` (REFONTE COMPLÈTE)
- ✅ Ordre: Pi → Suricata → DB → EC2 → UpdateDB
- ✅ Intégration DB à chaque étape
- ✅ Réconciliation AWS ↔ DB
- ✅ Health monitor SSH
- ✅ Upload clés SSH sur Pi et EC2
- ✅ Plus de dépendances SSM

### `webbapp/ids/deploy/pi_deployer.py`
- ✅ Méthode `install_shared_ssh_key()` pour upload clé
- ✅ Vérification existence avant overwrite

### `webbapp/ids/deploy/gui.py`
- ✅ `_ensure_local_ssh_key()` propose création si absente
- ✅ Message clair sur clé partagée

### `config.json`
- ✅ Recréé avec valeurs par défaut
- ✅ `ssh_key_path` pointant vers `/home/tor/.ssh/pi_key`

### `start.sh`
- ✅ Réparé (plus de venv, utilise `requirements.txt`)
- ✅ Gestion PEP668 "externally-managed"

## 🧪 Tests
- ✅ 17/17 tests passent
- ✅ Pas de régression

## 📝 Ce qui reste (optionnel)

### AWS Deployer - Nettoyage SSM
Les méthodes SSM sont toujours présentes dans `aws_deployer.py` mais **ne sont plus utilisées** par l'orchestrator:
- `_send_ssm_commands()`
- `_redeploy_elk_via_ssm()`
- `_log_docker_status()`
- `stop_elasticsearch()`
- `sync_instance_ssh_keys()` (remplacée par SSH pur)

**Décision:** Les garder pour compatibilité ou les supprimer ?

### GUI - Améliorations possibles
- Afficher état DB en temps réel
- Bouton "Sync DB with AWS"
- Panel dédié instances trackées

## 🚀 Utilisation

```bash
cd /home/tor/Downloads/ids2
./start.sh
```

1. Le GUI vérifie si `/home/tor/.ssh/pi_key` existe
2. Si non → propose de la créer
3. Deploy: cette clé est uploadée sur Pi ET EC2
4. Toutes les connexions utilisent cette clé unique
5. DB est mise à jour automatiquement
6. Health monitor SSH tourne en background

## 🔑 Clé SSH unique

**Emplacement:** `/home/tor/.ssh/pi_key` (+ `.pub`)

**Utilisée pour:**
- Local → Pi (SSH)
- Local → EC2 (SSH)
- Pi → EC2 (si besoin, clé uploadée sur Pi)

**Plus besoin de:**
- `ids2_ec2_key` (supprimé)
- Clés AWS séparées
- SSM pour accès EC2
