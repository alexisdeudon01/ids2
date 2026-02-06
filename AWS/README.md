# AWS Deployment - IDS2

## Structure

```
AWS/
├── datas/                      # Données AWS extraites → SQL
│   ├── 01_aws_account.sql
│   ├── 02_iam_users.sql
│   ├── 03_api_keys.sql
│   ├── 04_ec2_instances.sql
│   ├── 05_elk_credentials.sql  # ← Credentials Elasticsearch/Kibana
│   └── 06_deployment_config.sql
├── mysql/                      # MySQL Database (sur Raspberry Pi)
│   ├── Dockerfile
│   └── init.sql
├── app/                        # Application backend
│   ├── Dockerfile
│   └── ...
├── extract_aws_data.sh         # Extrait données AWS → datas/*.sql
├── deploy_db_to_pi.sh          # Deploy MySQL sur Pi via SSH
├── deploy_suricata_to_pi.sh    # Deploy Suricata IDS sur Pi via SSH
├── deploy_all.sh               # MASTER: déploie tout
├── monitor_db_coherence.py     # Monitor cohérence DB ↔ réalité
└── README.md
```

## 🚀 Déploiement Complet (Automatique)

### Script Master - Tout en un

```bash
cd /home/tor/Downloads/ids2/AWS
./deploy_all.sh
```

Ce script exécute dans l'ordre :
1. **Extract AWS data** → génère fichiers SQL dans `datas/`
2. **Deploy MySQL** → sur Pi avec données AWS préchargées
3. **Deploy Suricata** → IDS sur Pi

### Déploiement par Étapes

#### Étape 1 : Extraire données AWS

```bash
./extract_aws_data.sh
```

Génère 6 fichiers SQL dans `datas/` :
- Account AWS
- Utilisateurs IAM
- Clés API
- Instances EC2
- **Credentials Elasticsearch/Kibana** (elastic/admin)
- Configuration déploiement

#### Étape 2 : Déployer MySQL sur Pi

```bash
./deploy_db_to_pi.sh
```

Le script va :
1. ✅ Charger configuration depuis `config.json`
2. ✅ Tester connexion SSH au Pi
3. ✅ Copier Dockerfile + init.sql + tous les SQL de `datas/`
4. ✅ Installer Docker/docker-compose si nécessaire
5. ✅ Build + démarrer container MySQL
6. ✅ Charger toutes les données automatiquement
7. ✅ Vérifier que DB est prête

#### Étape 3 : Déployer Suricata IDS

```bash
./deploy_suricata_to_pi.sh
```

Le script va :
1. ✅ Installer Suricata
2. ✅ Mettre à jour les règles
3. ✅ Configurer l'interface réseau (`eth0` par défaut)
4. ✅ Créer service systemd
5. ✅ Démarrer Suricata

## 📊 Monitoring de Cohérence

Le script `monitor_db_coherence.py` vérifie **en continu** la cohérence entre :
- Base de données (Pi)
- AWS réel (instances EC2)
- Services Pi (SSH, Suricata, MySQL, Webapp)

### Utilisation

```bash
# Check unique
./monitor_db_coherence.py --once

# Monitoring continu (toutes les 10s)
./monitor_db_coherence.py

# Intervalle personnalisé (30s)
./monitor_db_coherence.py --interval 30
```

### Vérifications effectuées

Le monitor vérifie **automatiquement** :
- ✅ Health DB MySQL
- ✅ SSH Pi accessible
- ✅ SSH EC2 accessible
- ✅ Services actifs (Suricata, MySQL, Webapp)
- ✅ Cohérence instances DB ↔ AWS
- ✅ Auto-cleanup instances orphelines en DB
- ✅ Auto-ajout instances manquantes en DB
- ✅ Auto-update états/IPs

### Exemple de sortie

```
🔍 Coherence Check #1 - 2026-02-06 22:52:10
============================================================
📊 Database: ✅ OK
🔌 Pi SSH (192.168.178.66): ✅ OK
🛡️  Suricata: ✅ active
💾 MySQL: ✅ active
🌐 Webapp: ✅ active

🔄 Reconciliation:
   DB instances: 1
   AWS instances: 1
   ✅ DB and AWS are in sync

🔌 EC2 SSH (i-05ac0e0b0bc782cbd): ✅ OK
```

### Déploiement manuel

```bash
# 1. Connexion SSH au Pi
ssh -i /home/tor/.ssh/pi_key pi@192.168.178.66

# 2. Créer répertoire
sudo mkdir -p /opt/ids2/mysql
cd /opt/ids2

# 3. Copier fichiers depuis local
# (depuis votre PC)
scp -i /home/tor/.ssh/pi_key AWS/mysql/* pi@192.168.178.66:/opt/ids2/mysql/

# 4. Build et démarrer
cd /opt/ids2
sudo docker-compose -f docker-compose-mysql.yml up -d

# 5. Vérifier
sudo docker ps
sudo docker logs ids2-mysql
```

## Connexion à la base de données

### Depuis le Raspberry Pi

```bash
sudo docker exec -it ids2-mysql mysql -uids_user -padmin ids_db
```

### Depuis votre PC (si port 3306 accessible)

```bash
mysql -h 192.168.178.66 -P 3306 -uids_user -padmin ids_db
```

### Credentials

**MySQL Database:**
- **Database**: `ids_db`
- **User**: `ids_user`
- **Password**: `admin`
- **Root password**: `admin`
- **Host**: `192.168.178.66:3306` (Raspberry Pi)

**Elasticsearch:**
- **User**: `elastic`
- **Password**: `admin`
- **URL**: `http://[EC2_IP]:9200`

**Kibana:**
- **User**: `elastic`
- **Password**: `admin`
- **URL**: `http://[EC2_IP]:5601`

## Tables créées

### Tables AWS Audit
- `AWS_ACCOUNT` - Comptes AWS
- `IAM_USER` - Utilisateurs IAM
- `API_KEY` - Clés API AWS
- `RESOURCE` - Ressources AWS

### Tables IDS
- `alerts` - Alertes de sécurité Suricata
- `system_metrics` - Métriques système (CPU, RAM, etc.)
- `deployment_config` - Configurations de déploiement
- `ec2_instances` - Tracking instances EC2

## Maintenance

### Voir les logs

```bash
ssh -i /home/tor/.ssh/pi_key pi@192.168.178.66 'sudo docker logs ids2-mysql'
```

### Arrêter/Redémarrer

```bash
ssh -i /home/tor/.ssh/pi_key pi@192.168.178.66 'cd /opt/ids2 && sudo docker-compose -f docker-compose-mysql.yml stop'
ssh -i /home/tor/.ssh/pi_key pi@192.168.178.66 'cd /opt/ids2 && sudo docker-compose -f docker-compose-mysql.yml start'
```

### Backup

```bash
ssh -i /home/tor/.ssh/pi_key pi@192.168.178.66 \
  'sudo docker exec ids2-mysql mysqldump -uroot -padmin ids_db > /opt/ids2/backup.sql'
```

### Restore

```bash
ssh -i /home/tor/.ssh/pi_key pi@192.168.178.66 \
  'sudo docker exec -i ids2-mysql mysql -uroot -padmin ids_db < /opt/ids2/backup.sql'
```

## Données persistantes

Les données MySQL sont stockées dans `/opt/ids2/mysql/data` sur le Pi.

Pour sauvegarder :
```bash
ssh -i /home/tor/.ssh/pi_key pi@192.168.178.66 \
  'sudo tar czf /tmp/mysql-backup.tar.gz /opt/ids2/mysql/data'
  
scp -i /home/tor/.ssh/pi_key \
  pi@192.168.178.66:/tmp/mysql-backup.tar.gz \
  ./mysql-backup-$(date +%Y%m%d).tar.gz
```
