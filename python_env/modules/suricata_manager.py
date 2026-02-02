import logging
import os
import subprocess
import time
from base_component import BaseComponent
import logging
import os
import subprocess
import time
import signal # Import du module signal
from base_component import BaseComponent

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
        self.suricata_process = None # Initialiser le processus Suricata à None

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

    def start_suricata(self):
        """
        Démarre le processus Suricata sur l'hôte.
        """
        self.logger.info("Démarrage du processus Suricata sur l'hôte...")
        try:
            cmd = ["suricata", "-i", self.network_interface, "-c", self.suricata_config_path, "--set", f"outputs.0.eve-log.filename={self.log_output_path}"]
            self.suricata_process = subprocess.Popen(cmd, preexec_fn=os.setsid)
            self.logger.info(f"Processus Suricata démarré avec PID: {self.suricata_process.pid}")
            return True
        except FileNotFoundError:
            self.log_error("La commande 'suricata' n'a pas été trouvée. Assurez-vous que Suricata est installé sur l'hôte.")
            return False
        except Exception as e:
            self.log_error(f"Erreur lors du démarrage de Suricata", e)
            return False

    def stop_suricata(self):
        """
        Arrête le processus Suricata sur l'hôte.
        """
        if self.suricata_process and self.suricata_process.poll() is None:
            self.logger.info("Arrêt du processus Suricata...")
            try:
                os.killpg(os.getpgid(self.suricata_process.pid), signal.SIGTERM)
                self.suricata_process.wait(timeout=5)
                self.logger.info("Processus Suricata arrêté.")
                return True
            except Exception as e:
                self.log_error(f"Erreur lors de l'arrêt de Suricata", e)
                return False
        self.logger.info("Le processus Suricata n'était pas en cours d'exécution.")
        return True

    def restart_suricata(self):
        """
        Redémarre le processus Suricata sur l'hôte.
        """
        self.logger.info("Redémarrage du processus Suricata...")
        self.stop_suricata()
        time.sleep(2)
        return self.start_suricata()

    def run(self):
        """
        Méthode principale pour le SuricataManager.
        """
        self.logger.info("SuricataManager démarré. La génération de la configuration est appelée par le superviseur.")
        while not self.is_shutdown_requested():
            time.sleep(5)
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
    """
    with open('temp_config.yaml', 'w') as f:
        f.write(temp_config_content)

    os.makedirs('suricata', exist_ok=True)
    os.makedirs('suricata/rules', exist_ok=True)

    try:
        config_mgr = ConfigManager(config_path='temp_config.yaml')
        manager = multiprocessing.Manager()
        shared_state = manager.dict({
            'last_error': ''
        })
        shutdown_event = multiprocessing.Event()

        suricata_mgr = SuricataManager(shared_state, config_mgr, shutdown_event)
        
        print("\nTest de génération de la configuration Suricata...")
        if suricata_mgr.generate_suricata_config():
            print(f"Contenu de {suricata_mgr.suricata_config_path} :\n")
            with open(suricata_mgr.suricata_config_path, 'r') as f:
                print(f.read())

        print("\nTest de démarrage/arrêt de Suricata (simulé)...")
        # Pour un test réel, Suricata devrait être installé sur l'hôte
        # if suricata_mgr.start_suricata():
        #     print("Suricata démarré. Attente de 10 secondes...")
        #     time.sleep(10)
        #     print("Arrêt de Suricata...")
        #     suricata_mgr.stop_suricata()
        # else:
        #     print("Échec du démarrage de Suricata.")

    except Exception as e:
        logging.error(f"Erreur lors du test de SuricataManager: {e}")
    finally:
        if os.path.exists('temp_config.yaml'):
            os.remove('temp_config.yaml')
        if os.path.exists('suricata/suricata.yaml'):
            os.remove('suricata/suricata.yaml')
        if os.path.exists('suricata/rules'):
            subprocess.run(["rm", "-rf", "suricata/rules"], check=True, capture_output=True, text=True)
        if os.path.exists('suricata'):
            os.rmdir('suricata')
