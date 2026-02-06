# Refactoring SSH + DB Integration

## ✅ Complété

### 1. Base de données étendue
- ✅ Ajout table `ec2_instances` pour tracking
- ✅ Méthodes: `upsert_ec2_instance()`, `get_ec2_instances()`, `delete_ec2_instance()`
- ✅ Ajout `ssh_key_path` dans `deployment_config`
- ✅ Méthode `get_latest_deployment_config()` pour récupérer dernière config

### 2. Orchestrator refactoré
- ✅ Ordre correct: Pi → Suricata → DB → EC2 → Update DB
- ✅ Intégration DB dans workflow:
  - Vérification instances existantes en DB
  - Réconciliation AWS ↔ DB
  - Update DB après déploiement EC2
  - Sauvegarde config déploiement
- ✅ Health monitor SSH toutes les 10s (thread dédié)
- ✅ Suppression dépendances SSM dans orchestrator

### 3. Pi Deployer
- ✅ Méthode `install_shared_ssh_key()` pour upload clé sur Pi
- ✅ Vérification existence avant overwrite

## 🔧 En cours / À finaliser

### 4. AWS Deployer - Retrait SSM
- ⚠️ Méthode `sync_instance_ssh_keys()` existe mais utilise encore SSM
- ⚠️ Besoin: `upload_ssh_key_to_instance()` en SSH pur (sans SSM)
- ⚠️ Retirer: `_send_ssm_commands()`, `_redeploy_elk_via_ssm()`, `_log_docker_status()`

### 5. GUI - Message SSH key
- ⚠️ `_ensure_local_ssh_key()` fonctionne mais message peut être amélioré
- ⚠️ Clarifier que c'est la clé partagée Pi/EC2/local

## 📝 Actions restantes

1. **AWS Deployer**: Implémenter `upload_ssh_key_to_instance()` en SSH pur
   - Connexion SSH directe à l'instance EC2
   - Upload clé privée + publique
   - Ajout authorized_keys
   - Test connexion

2. **AWS Deployer**: Retirer toutes méthodes SSM
   - `_send_ssm_commands()`
   - `_redeploy_elk_via_ssm()`
   - `_log_docker_status()`
   - `stop_elasticsearch()` (qui utilise SSM)

3. **Orchestrator**: Appeler `upload_ssh_key_to_instance()` au lieu de `sync_instance_ssh_keys()`

4. **GUI**: Améliorer message "SSH key not found"
   - Clarifier: "Clé SSH partagée (Pi/EC2/local)"
   - Proposer création si absente

5. **Tests**: Mettre à jour tests unitaires
   - Nouveaux champs DB
   - Nouvelles méthodes orchestrator
   - Retrait SSM

## 🎯 Objectif final

**Une seule clé SSH** (`/home/tor/.ssh/pi_key`) pour:
- Connexion locale → Pi
- Connexion locale → EC2
- Connexion Pi → EC2 (si besoin)

**Tout en SSH**, plus de SSM AWS.

**DB intégrée** avec vérification cohérence monde réel ↔ DB.
