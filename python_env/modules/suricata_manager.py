import logging
import os
import subprocess
import time
from base_component import BaseComponent
from docker_manager import DockerManager # Pour interagir avec le conteneur Suricata

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s')

class SuricataManager(BaseComponent):
    """
    Gère la configuration et le cycle de vie de Suricata.
    """
    def __init__(self, shared_state, config_manager, shutdown_event=None):
        super().__init__(shared_state, config_manager, shutdown_event)
        self.suricata_config_path = self.get_config('suricata.config_path', 'suricata/suricata.yaml')
        self.log_output_path = self.get_config('suricata.log_path', '/mnt/ram_logs/eve.json')
        self.network_interface = self.get_config('raspberry_pi.network_interface', 'eth0')
        self.eve_log_options = self.get_config('suricata.eve_log_options', {
            'payload': False,
            'packet': False,
            'http': True,
            'dns': True,
            'tls': True,
        })
        self.docker_manager = DockerManager(shared_state, config_manager, shutdown_event) # Initialiser DockerManager

    def generate_suricata_config(self):
        """
        Génère le fichier de configuration suricata.yaml basé sur les paramètres du projet.
        """
        self.logger.info(f"Génération du fichier de configuration Suricata à : {self.suricata_config_path}")

        os.makedirs(os.path.dirname(self.suricata_config_path), exist_ok=True)
        
        log_dir = os.path.dirname(self.log_output_path)
        if not os.path.exists(log_dir):
            self.logger.warning(f"Le répertoire de logs RAM '{log_dir}' n'existe pas. Il devrait être créé ou monté au démarrage.")

        eve_log_types_config = ""
        for option, enabled in self.eve_log_options.items():
            if enabled:
                eve_log_types_config += f"            {option}: yes\n"

        suricata_config_content = f"""
# Configuration Suricata pour IDS2 SOC Pipeline
# Généré par l'agent Python

# Configuration de l'interface réseau
default-log-dir: /var/log/suricata # Répertoire par défaut pour les logs internes de Suricata
outputs:
  - eve-log:
      enabled: yes
      filetype: regular
      filename: {self.log_output_path.split('/')[-1]} # Juste le nom du fichier, le chemin est géré par le volume Docker
      types:
        - alert:
{eve_log_types_config}
"""
        try:
            with open(self.suricata_config_path, 'w') as f:
                f.write(suricata_config_content)
            self.logger.info("Fichier de configuration Suricata généré avec succès.")
            return True
        except IOError as e:
            self.log_error(f"Erreur lors de l'écriture du fichier de configuration Suricata", e)
            return False

    def start_suricata_container(self):
        """
        Démarre le conteneur Suricata via Docker Compose.
        """
        self.logger.info("Démarrage du conteneur Suricata...")
        return self.docker_manager._run_docker_compose_command("up suricata", detach=True)

    def stop_suricata_container(self):
        """
        Arrête le conteneur Suricata via Docker Compose.
        """
        self.logger.info("Arrêt du conteneur Suricata...")
        return self.docker_manager._run_docker_compose_command("stop suricata")

    def restart_suricata_container(self):
        """
        Redémarre le conteneur Suricata via Docker Compose.
        """
        self.logger.info("Redémarrage du conteneur Suricata...")
        return self.docker_manager._run_docker_compose_command("restart suricata")

    def run(self):
        """
        Méthode principale pour le SuricataManager (peut être vide si l'orchestration est dans main.py).
        """
        self.logger.info("SuricataManager démarré. La génération de la configuration est appelée par le superviseur.")
        # Le superviseur appelle generate_suricata_config() et gère le démarrage du conteneur.
        # Ce processus pourrait surveiller l'état de Suricata si nécessaire.
        while not self.is_shutdown_requested():
            time.sleep(5) # Simple boucle d'attente
        self.logger.info("SuricataManager arrêté.")


# Exemple d'utilisation (pour les tests)
if __name__ == "__main__":
    from config_manager import ConfigManager
    import multiprocessing
    
    # Créer un fichier config.yaml temporaire pour le test
    temp_config_content = """
    raspberry_pi:
      network_interface: "eth0"
    suricata:
      log_path: "/tmp/eve.json"
      config_path: "suricata/suricata.yaml"
      eve_log_options:
        payload: yes
        http: yes
    docker: # Nécessaire pour DockerManager
      compose_file: "docker/docker-compose.yml"
      required_services: ["suricata"]
    """
    with open('temp_config.yaml', 'w') as f:
        f.write(temp_config_content)

    # Créer un docker-compose.yml temporaire pour le test
    os.makedirs('docker', exist_ok=True)
    with open('docker/docker-compose.yml', 'w') as f:
        f.write("""
version: '3.8'
services:
  suricata:
    image: oisf/suricata:6.0.10
    command: ["-i", "eth0", "-c", "/etc/suricata/suricata.yaml", "--set", "outputs.0.eve-log.filename=/mnt/ram_logs/eve.json"]
    network_mode: "host"
    volumes:
      - ./suricata.yaml:/etc/suricata/suricata.yaml:ro
      - /mnt/ram_logs:/mnt/ram_logs
      - ./rules:/etc/suricata/rules:ro
    cap_add:
      - NET_ADMIN
      - NET_RAW
    privileged: true
    deploy:
      resources:
        limits:
          cpus: '0.1'
          memory: 64M
""")
    os.makedirs('suricata', exist_ok=True) # Créer le répertoire pour suricata.yaml
    os.makedirs('suricata/rules', exist_ok=True) # Créer le répertoire pour les règles

    try:
        config_mgr = ConfigManager(config_path='temp_config.yaml')
        manager = multiprocessing.Manager()
        shared_state = manager.dict({
            'last_error': '',
            'docker_healthy': False # Ajout pour DockerManager
        })
        shutdown_event = multiprocessing.Event()

        suricata_mgr = SuricataManager(shared_state, config_mgr, shutdown_event)
        
        print("\nTest de génération de la configuration Suricata...")
        if suricata_mgr.generate_suricata_config():
            print(f"Contenu de {suricata_mgr.suricata_config_path} :\n")
            with open(suricata_mgr.suricata_config_path, 'r') as f:
                print(f.read())

        print("\nTest de démarrage du conteneur Suricata (simulé)...")
        # Le démarrage réel nécessiterait un démon Docker fonctionnel
        # if suricata_mgr.start_suricata_container():
        #     print("Conteneur Suricata démarré.")
        #     time.sleep(5)
        #     print("Arrêt du conteneur Suricata...")
        #     suricata_mgr.stop_suricata_container()
        # else:
        #     print("Échec du démarrage du conteneur Suricata.")

    except Exception as e:
        logging.error(f"Erreur lors du test de SuricataManager: {e}")
    finally:
        if os.path.exists('temp_config.yaml'):
            os.remove('temp_config.yaml')
        if os.path.exists('suricata/suricata.yaml'):
            os.remove('suricata/suricata.yaml')
        if os.path.exists('suricata/rules'):
            os.rmdir('suricata/rules')
        if os.path.exists('suricata'):
            os.rmdir('suricata')
        if os.path.exists('docker/docker-compose.yml'):
            os.remove('docker/docker-compose.yml')
        if os.path.exists('docker'):
            subprocess.run(["rm", "-rf", "docker"], check=True, capture_output=True, text=True)
