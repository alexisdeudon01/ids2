import logging
import os
import subprocess
import time
import json # Pour le mapping ECS plus détaillé
from base_component import BaseComponent # Import de BaseComponent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s')

class VectorManager(BaseComponent): # Hériter de BaseComponent
    """
    Gère la configuration et le cycle de vie de Vector.
    """
    def __init__(self, shared_state, config_manager, shutdown_event=None): # Ajuster l'ordre des arguments
        super().__init__(shared_state, config_manager, shutdown_event) # Appel du constructeur parent
        self.vector_config_path = self.get_config('vector.config_path', 'vector/vector.toml')
        self.log_read_path = self.get_config('vector.log_read_path', '/mnt/ram_logs/eve.json')
        self.opensearch_endpoint = self.get_config('aws.opensearch_endpoint')
        self.aws_region = self.get_config('aws.region')
        self.redis_host = self.get_config('redis.host')
        self.redis_port = self.get_config('redis.port')
        self.vector_disk_buffer_max_size = self.get_config('vector.disk_buffer_max_size', '100 GiB')
        self.vector_redis_buffer_max_size = self.get_config('vector.redis_buffer_max_size', '10 GiB')
        self.vector_opensearch_buffer_max_size = self.get_config('vector.opensearch_buffer_max_size', '50 GiB')
        self.vector_batch_max_events = self.get_config('vector.batch_max_events', 500) # Optimisé pour Pi
        self.vector_batch_timeout_secs = self.get_config('vector.batch_timeout_secs', 2)

    def generate_vector_config(self):
        """
        Génère le fichier de configuration vector.toml basé sur les paramètres du projet.
        """
        self.logger.info(f"Génération du fichier de configuration Vector à : {self.vector_config_path}")

        os.makedirs(os.path.dirname(self.vector_config_path), exist_ok=True)

        # Mapping ECS plus détaillé basé sur l'exemple du README
        ecs_remap_script = '''
  . = parse_json!(.message)
  
  # Champs communs
  . @timestamp = del(.timestamp)
  .event.kind = "event" # Par défaut, sera écrasé si alerte
  .event.category = "network"

  # Mapping IP source/destination
  if exists(.src_ip) { .source.ip = del(.src_ip) }
  if exists(.dest_ip) { .destination.ip = del(.dest_ip) }
  if exists(.src_port) { .source.port = del(.src_port) }
  if exists(.dest_port) { .destination.port = del(.dest_port) }
  if exists(.proto) { .network.protocol = del(.proto) }

  # Mapping spécifique aux alertes Suricata
  if exists(.event_type) && .event_type == "alert" {
    .event.kind = "alert"
    .event.category = "network"
    .event.type = "info" # Ou "detection", "threat"
    if exists(.alert) {
      .suricata.signature = .alert.signature
      .suricata.severity = .alert.severity
      del(.alert)
    }
    del(.event_type)
  }
'''

        vector_config_content = f"""
# Configuration Vector pour IDS2 SOC Pipeline

# Source : Lecture des logs Suricata
[sources.suricata_logs]
type = "file"
include = ["{self.log_read_path}"]
read_from = "beginning"
fingerprint_bytes = 1024

# Transformation : Parser les logs JSON de Suricata et mapper vers ECS
[transforms.parse_json_ecs]
type = "remap"
inputs = ["suricata_logs"]
source = '''{ecs_remap_script}'''

# Tampon disque pour Vector (obligatoire pour la résilience)
[buffers.disk_buffer]
type = "disk"
path = "/var/lib/vector/buffer"
max_size = "{self.vector_disk_buffer_max_size}"
when_full = "block"

# Sink : Envoi à Redis (pour la backpressure et comme buffer intermédiaire)
[sinks.redis_sink]
type = "redis"
inputs = ["parse_json_ecs"]
address = "{self.redis_host}:{self.redis_port}"
key = "vector_logs"
encoding = "json"
batch.max_events = {self.vector_batch_max_events}
batch.timeout_secs = {self.vector_batch_timeout_secs}
healthcheck.enabled = true
buffer.type = "disk"
buffer.path = "/var/lib/vector/redis_buffer"
buffer.max_size = "{self.vector_redis_buffer_max_size}"

# Sink : Envoi à AWS OpenSearch
[sinks.opensearch_sink]
type = "elasticsearch"
inputs = ["parse_json_ecs"]
endpoint = "{self.opensearch_endpoint}"
index = "{self.get_config('vector.index_pattern', 'suricata-ids2-%Y.%m.%d')}" # Index quotidien, configurable
auth.strategy = "aws"
auth.region = "{self.aws_region}"
compression = "gzip"
batch.max_events = {self.vector_batch_max_events}
batch.timeout_secs = {self.vector_batch_timeout_secs}
request.timeout_secs = 30
healthcheck.enabled = true
buffer.type = "disk"
buffer.path = "/var/lib/vector/opensearch_buffer"
buffer.max_size = "{self.vector_opensearch_buffer_max_size}"

# Note sur la stratégie de basculement :
# Vector envoie les données à tous les sinks configurés.
# Si un sink est indisponible, son buffer disque prend le relais.
# La description "Vector -> Redis -> OpenSearch" dans le README peut être interprétée
# comme une chaîne logique de traitement, où Redis agit comme un tampon pour OpenSearch.
# La configuration actuelle de Vector avec des buffers disques pour chaque sink
# assure la résilience et la backpressure. Si Redis doit être un point de passage
# obligatoire avant OpenSearch, une configuration plus complexe avec des "routes"
# conditionnelles ou un sink "fan-out" vers Redis puis un autre source/sink de Redis vers OpenSearch
# serait nécessaire. Pour la simplicité et la résilience, la configuration actuelle est efficace.
"""
        try:
            with open(self.vector_config_path, 'w') as f:
                f.write(vector_config_content)
            self.logger.info("Fichier de configuration Vector généré avec succès.")
            return True
        except IOError as e:
            self.log_error(f"Erreur lors de l'écriture du fichier de configuration Vector", e)
            return False

    def check_vector_health(self):
        """
        Vérifie la santé de Vector (via Docker).
        """
        # La santé de Vector est vérifiée par DockerManager.check_stack_health
        # Ici, nous mettons à jour l'état partagé en fonction de la santé Docker
        vector_healthy = self.shared_state.get('docker_healthy', False) # Supposons que docker_healthy implique vector_healthy
        self.update_shared_state('vector_healthy', vector_healthy)
        if vector_healthy:
            self.logger.info("Le conteneur Vector est sain (selon DockerManager).")
            return True
        else:
            self.logger.warning("Le conteneur Vector n'est pas sain.")
            self.log_error("Le conteneur Vector n'est pas sain.")
            return False

# Exemple d'utilisation (pour les tests)
if __name__ == "__main__":
    from config_manager import ConfigManager
    import multiprocessing
    
    # Créer un fichier config.yaml temporaire pour le test
    temp_config_content = """
    vector:
      config_path: "vector/vector.toml"
      log_read_path: "/tmp/eve.json"
      disk_buffer_max_size: "50 GiB"
      redis_buffer_max_size: "5 GiB"
      opensearch_buffer_max_size: "25 GiB"
      batch_max_events: 750
      batch_timeout_secs: 3
      index_pattern: "suricata-test-%Y.%m.%d"
    aws:
      opensearch_endpoint: "https://your-opensearch-domain.eu-west-1.es.amazonaws.com"
      region: "eu-west-1"
    redis:
      host: "localhost"
      port: 6379
    """
    with open('temp_config.yaml', 'w') as f:
        f.write(temp_config_content)

    try:
        config_mgr = ConfigManager(config_path='temp_config.yaml')
        manager = multiprocessing.Manager()
        shared_state = manager.dict({
            'docker_healthy': False,
            'vector_healthy': False,
            'last_error': ''
        })
        shutdown_event = multiprocessing.Event()

        vector_mgr = VectorManager(shared_state, config_mgr, shutdown_event)

        print("\nTest de génération de la configuration Vector...")
        if vector_mgr.generate_vector_config():
            print(f"Contenu de {vector_mgr.vector_config_path} :\n")
            with open(vector_mgr.vector_config_path, 'r') as f:
                print(f.read())
        
        print("\nTest de vérification de la santé de Vector (simulé)...")
        shared_state['docker_healthy'] = True
        print(f"Santé de Vector : {vector_mgr.check_vector_health()}")
        shared_state['docker_healthy'] = False
        print(f"Santé de Vector : {vector_mgr.check_vector_health()}")

    except Exception as e:
        logging.error(f"Erreur lors du test de VectorManager: {e}")
    finally:
        if os.path.exists('temp_config.yaml'):
            os.remove('temp_config.yaml')
        if os.path.exists('vector/vector.toml'):
            os.remove('vector/vector.toml')
        if os.path.exists('vector'):
            os.rmdir('vector')
