import multiprocessing
import time
import logging
import os
import sys

# Ajouter le répertoire des modules au PYTHONPATH
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

from config_manager import ConfigManager
from resource_controller import ResourceController
from aws_manager import AWSManager
from connectivity_async import ConnectivityAsync
from docker_manager import DockerManager
from vector_manager import VectorManager
from suricata_manager import SuricataManager
from metrics_server import MetricsServer
from git_workflow import GitWorkflow
from suricata_rules_manager import SuricataRulesManager # Import du nouveau module
from base_component import BaseComponent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s')

class AgentSupervisor:
    """
    Processus superviseur de l'agent multi-processus.
    Démarre, surveille et gère les processus enfants.
    """
    def __init__(self, config_path='config.yaml'):
        self.config_manager = ConfigManager(config_path)
        self.manager = multiprocessing.Manager()
        self.shared_state = self.manager.dict({
            'cpu_usage': 0.0,
            'ram_usage': 0.0,
            'throttling_level': 0,
            'aws_ready': False,
            'vector_ready': False,
            'redis_ready': False,
            'pipeline_ok': False,
            'docker_healthy': False,
            'last_error': '',
            'ingestion_rate_increment': 0,
            'error_increment': 0,
            'redis_queue_depth': 0,
            'suricata_rules_updated': False, # Ajout pour le suivi des règles
        })
        self.shutdown_event = multiprocessing.Event()
        self.processes = []
        self.process_map = {
            "ResourceController": ResourceController,
            "ConnectivityAsync": ConnectivityAsync,
            "MetricsServer": MetricsServer,
            "SuricataRulesManager": SuricataRulesManager, # Ajout du gestionnaire de règles
            # "VerificationProcess": VerificationProcess,
        }
        self.docker_manager = DockerManager(self.shared_state, self.config_manager)
        self.vector_manager = VectorManager(self.shared_state, self.config_manager)
        self.suricata_manager = SuricataManager(self.shared_state, self.config_manager)
        self.git_workflow = GitWorkflow(self.shared_state, self.config_manager)

    def _start_child_process(self, name, target_class):
        """
        Démarre un processus enfant et l'ajoute à la liste des processus.
        Passe l'événement d'arrêt aux processus enfants.
        """
        instance = target_class(self.shared_state, self.config_manager, self.shutdown_event)
        
        process = multiprocessing.Process(target=instance.run, name=name)
        self.processes.append(process)
        process.start()
        logging.info(f"Processus enfant '{name}' démarré (PID: {process.pid}).")
        return process

    def _monitor_processes(self):
        """
        Surveille la vivacité des processus enfants et les redémarre si nécessaire.
        """
        while not self.shutdown_event.is_set():
            for p in self.processes:
                if not p.is_alive():
                    logging.error(f"Processus '{p.name}' est mort. Redémarrage...")
                    # Implémenter une logique de backoff si nécessaire
                    new_process = self._start_child_process(p.name, self.process_map[p.name])
                    self.processes.remove(p)
                    self.processes.append(new_process)
            time.sleep(5) # Vérifier toutes les 5 secondes

    def _graceful_shutdown(self):
        """
        Gère l'arrêt propre de tous les processus enfants.
        """
        logging.info("Signal d'arrêt reçu. Arrêt des processus enfants...")
        self.shutdown_event.set() # Signaler aux enfants de s'arrêter

        for p in self.processes:
            if p.is_alive():
                p.terminate() # Tenter un arrêt doux
                p.join(timeout=5) # Attendre la terminaison
                if p.is_alive():
                    logging.warning(f"Processus '{p.name}' n'a pas répondu à l'arrêt doux. Forçage de l'arrêt.")
                    p.kill()
            logging.info(f"Processus '{p.name}' arrêté.")
        
        # Arrêter la pile Docker
        self.docker_manager.stop_docker_stack()
        logging.info("Tous les processus enfants et services Docker sont arrêtés.")

    def run(self):
        """
        Point d'entrée principal du superviseur de l'agent.
        """
        logging.info("Agent IDS2 SOC démarré.")

        # 1. Vérification de la branche Git
        if not self.git_workflow.check_branch():
            logging.critical("L'agent doit s'exécuter sur la branche 'dev'. Arrêt.")
            sys.exit(1)

        # 2. Préparation de la pile Docker (en parallèle)
        # La construction et le démarrage de Docker peuvent être longs, mais ne bloquent pas la génération de config
        docker_prep_success = self.docker_manager.prepare_docker_stack()
        if not docker_prep_success:
            logging.critical("Échec de la préparation de la pile Docker. Arrêt.")
            sys.exit(1)
        
        # 3. Génération des configurations (en parallèle)
        self.vector_manager.generate_vector_config()
        self.suricata_manager.generate_suricata_config()

        # Démarrer les processus de contrôle et de métriques tôt
        self._start_child_process("ResourceController", ResourceController)
        self._start_child_process("MetricsServer", MetricsServer)
        self._start_child_process("SuricataRulesManager", SuricataRulesManager) # Démarrer le gestionnaire de règles

        # Attendre que la pile Docker soit saine (séquentiel)
        logging.info("Attente de la santé de la pile Docker...")
        max_wait_time = 120 # secondes
        start_time = time.time()
        while not self.shared_state.get('docker_healthy', False) and (time.time() - start_time) < max_wait_time:
            self.docker_manager.check_stack_health() # Met à jour shared_state['docker_healthy']
            time.sleep(5)
        
        if not self.shared_state.get('docker_healthy', False):
            logging.critical("La pile Docker n'est pas devenue saine à temps. Arrêt.")
            self._graceful_shutdown()
            sys.exit(1)
        logging.info("Pile Docker saine.")

        # Démarrer le processus de connectivité (ASYNC)
        self._start_child_process("ConnectivityAsync", ConnectivityAsync)

        # Attendre le succès DNS + TLS (séquentiel)
        logging.info("Attente de la connectivité DNS et TLS...")
        start_time = time.time()
        while not self.shared_state.get('aws_ready', False) and (time.time() - start_time) < max_wait_time:
            time.sleep(5) # ConnectivityAsync met à jour aws_ready
        
        if not self.shared_state.get('aws_ready', False):
            logging.critical("Échec de la connectivité AWS (DNS/TLS). Arrêt.")
            self._graceful_shutdown()
            sys.exit(1)
        logging.info("Connectivité AWS (DNS/TLS) établie.")

        # Test d'ingestion de masse OpenSearch (séquentiel)
        # Ce test est implicitement fait par ConnectivityAsync.check_opensearch_bulk_test
        # et son résultat est reflété dans shared_state['aws_ready'] et shared_state['pipeline_ok']
        # Si aws_ready est True ici, cela signifie que le test bulk a réussi.

        # L'agent est maintenant activé et le pipeline est opérationnel
        self.shared_state['pipeline_ok'] = True
        logging.info("Pipeline IDS2 SOC entièrement opérationnel.")

        # Boucle principale du superviseur
        try:
            self._monitor_processes()
        except KeyboardInterrupt:
            logging.info("Interruption clavier détectée.")
        finally:
            self._graceful_shutdown()

# Point d'entrée de l'application
if __name__ == "__main__":
    import subprocess # Ajout de l'import subprocess
    
    # Créer un fichier config.yaml temporaire pour le test
    temp_config_content = """
    raspberry_pi:
      ip: "192.168.178.66"
      network_interface: "eth0"
      cpu_limit_percent: 70
      ram_limit_percent: 70
      swap_size_gb: 2

    suricata:
      log_path: "/mnt/ram_logs/eve.json"
      config_path: "suricata/suricata.yaml"

    vector:
      config_path: "vector/vector.toml"
      log_read_path: "/mnt/ram_logs/eve.json"

    redis:
      host: "localhost"
      port: 6379
      db: 0

    aws:
      opensearch_endpoint: "https://your-opensearch-domain.eu-west-1.es.amazonaws.com"
      region: "eu-west-1"
      profile: "moi33"

    prometheus:
      port: 9100

    docker:
      vector_cpu: 1.0
      vector_ram_mb: 1024
      redis_cpu: 0.5
      redis_ram_mb: 512
      prometheus_cpu: 0.5
      prometheus_ram_mb: 512
      grafana_cpu: 0.5
      grafana_ram_mb: 512

    git:
      branch: "dev"
    connectivity_check_interval: 5
    """
    with open('temp_config.yaml', 'w') as f:
        f.write(temp_config_content)

    # Créer des fichiers de configuration factices pour les managers
    os.makedirs('vector', exist_ok=True)
    with open('vector/vector.toml', 'w') as f:
        f.write("[sources.dummy]\ntype = \"null\"")
    os.makedirs('suricata', exist_ok=True)
    with open('suricata/suricata.yaml', 'w') as f:
        f.write("outputs: []")
    
    # Créer un docker-compose.yml temporaire pour le test
    os.makedirs('docker', exist_ok=True)
    with open('docker/docker-compose.yml', 'w') as f:
        f.write("""
version: '3.8'
services:
  vector:
    image: timberio/vector:0.34.0-alpine
    command: ["vector", "--config", "/etc/vector/vector.toml"]
    volumes:
      - ./vector/vector.toml:/etc/vector/vector.toml:ro
      - /mnt/ram_logs:/mnt/ram_logs
    deploy:
      resources:
        limits:
          cpus: '0.1'
          memory: 64M
  redis:
    image: redis:7-alpine
    deploy:
      resources:
        limits:
          cpus: '0.1'
          memory: 64M
  prometheus:
    image: prom/prometheus:v2.47.0
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    volumes:
      - ./docker/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    deploy:
      resources:
        limits:
          cpus: '0.1'
          memory: 64M
  grafana:
    image: grafana/grafana:10.1.5
    volumes:
      - ./docker/grafana:/var/lib/grafana
    deploy:
      resources:
        limits:
          cpus: '0.1'
          memory: 64M
""")
    # Créer un prometheus.yml temporaire
    with open('docker/prometheus.yml', 'w') as f:
        f.write("""
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
  - job_name: 'ids2-agent'
    static_configs:
      - targets: ['localhost:9100'] # L'agent expose ses métriques ici
""")

    # Initialiser un dépôt Git temporaire pour le test
    os.makedirs('temp_git_repo', exist_ok=True)
    os.chdir('temp_git_repo')
    subprocess.run(["git", "init"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "checkout", "-b", "dev"], check=True, capture_output=True, text=True)
    with open('dummy_file.txt', 'w') as f:
        f.write("Dummy content")
    subprocess.run(["git", "add", "dummy_file.txt"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "Initial commit for agent test"], check=True, capture_output=True, text=True)
    # Simuler une remote
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/test/test.git"], check=True, capture_output=True, text=True)
    os.chdir('..') # Revenir au répertoire parent

    try:
        supervisor = AgentSupervisor(config_path='temp_config.yaml')
        supervisor.run()
    except Exception as e:
        logging.critical(f"Erreur critique dans le superviseur de l'agent : {e}")
    finally:
        # Nettoyage des fichiers temporaires
        if os.path.exists('temp_config.yaml'):
            os.remove('temp_config.yaml')
        if os.path.exists('vector/vector.toml'):
            os.remove('vector/vector.toml')
        if os.path.exists('vector'):
            os.rmdir('vector')
        if os.path.exists('suricata/suricata.yaml'):
            os.remove('suricata/suricata.yaml')
        if os.path.exists('suricata'):
            os.rmdir('suricata')
        if os.path.exists('docker/docker-compose.yml'):
            os.remove('docker/docker-compose.yml')
        if os.path.exists('docker/prometheus.yml'):
            os.remove('docker/prometheus.yml')
        if os.path.exists('docker/grafana'):
            os.rmdir('docker/grafana')
        if os.path.exists('docker'):
            os.rmdir('docker')
        if os.path.exists('temp_git_repo'):
            subprocess.run(["rm", "-rf", "temp_git_repo"], check=True, capture_output=True, text=True)
