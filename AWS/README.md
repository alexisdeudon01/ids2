# AWS Deployment - IDS2

## Structure

```
AWS/
├── datas/              # Données persistantes (*.db, volumes MySQL)
│   └── .gitkeep
├── mysql/              # MySQL Database (déployé sur Raspberry Pi)
│   ├── Dockerfile
│   └── init.sql
├── app/                # Application backend
│   ├── Dockerfile
│   └── ...
├── deploy_db_to_pi.sh  # Script de déploiement MySQL sur Pi via SSH
└── README.md
```

## Déploiement de la base de données sur Raspberry Pi

La base de données MySQL est déployée **sur le Raspberry Pi**, pas sur l'instance EC2.

### Prérequis

- Raspberry Pi accessible via SSH
- Docker et docker-compose installés sur le Pi
- Clé SSH configurée dans `config.json`

### Déploiement automatique

```bash
cd /home/tor/Downloads/ids2/AWS
./deploy_db_to_pi.sh
```

Le script va :
1. ✅ Charger la configuration depuis `config.json`
2. ✅ Tester la connexion SSH au Pi
3. ✅ Copier les fichiers MySQL (Dockerfile, init.sql)
4. ✅ Créer docker-compose.yml sur le Pi
5. ✅ Installer Docker/docker-compose si nécessaire
6. ✅ Build et démarrer le container MySQL
7. ✅ Vérifier que la DB est prête
8. ✅ Afficher les infos de connexion

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

- **Database**: `ids_db`
- **User**: `ids_user`
- **Password**: `admin`
- **Root password**: `admin`

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
