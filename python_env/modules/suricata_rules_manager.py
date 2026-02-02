import logging
import os
import subprocess
import time
from base_component import BaseComponent

class SuricataRulesManager(BaseComponent):
    """
    Gère le téléchargement, la mise à jour et l'application des règles Suricata.
    """
    def __init__(self, shared_state, config_manager, shutdown_event=None):
        super().__init__(shared_state, config_manager, shutdown_event)
        self.rules_path = self.get_config('suricata.rules_path', 'suricata/rules')
        self.oinkcode = self.get_config('suricata.oinkcode') # Code pour les règles ET Pro
        self.rule_sources = self.get_config('suricata.rule_sources', [
            "https://rules.emergingthreats.net/open/suricata-6.0.0/emerging.rules.tar.gz"
        ])
        self.update_interval = self.get_config('suricata.rules_update_interval_hours', 24) * 3600 # En secondes

    def _download_rules(self, url, destination_dir):
        """
        Télécharge un fichier de règles et l'extrait.
        """
        try:
            self.logger.info(f"Téléchargement des règles depuis : {url}")
            # Utiliser curl pour le téléchargement
            subprocess.run(["curl", "-sSL", url, "-o", os.path.join(destination_dir, "rules.tar.gz")], check=True, capture_output=True)
            self.logger.info(f"Extraction des règles dans : {destination_dir}")
            subprocess.run(["tar", "-xzf", os.path.join(destination_dir, "rules.tar.gz"), "-C", destination_dir, "--strip-components=1"], check=True, capture_output=True)
            os.remove(os.path.join(destination_dir, "rules.tar.gz"))
            self.logger.info("Règles téléchargées et extraites avec succès.")
            return True
        except subprocess.CalledProcessError as e:
            self.log_error(f"Échec du téléchargement/extraction des règles depuis {url}: {e.stderr.strip()}", e)
            return False
        except Exception as e:
            self.log_error(f"Erreur inattendue lors du téléchargement des règles depuis {url}", e)
            return False

    def update_rules(self):
        """
        Met à jour toutes les sources de règles configurées.
        """
        self.logger.info("Mise à jour des règles Suricata...")
        os.makedirs(self.rules_path, exist_ok=True) # S'assurer que le répertoire des règles existe

        success = True
        for source_url in self.rule_sources:
            # Gérer les règles ET Pro si oinkcode est fourni
            if "emergingthreats.net/rules/etpro" in source_url and self.oinkcode:
                url_with_oink = source_url.replace("oinkcode=", f"oinkcode={self.oinkcode}")
                if not self._download_rules(url_with_oink, self.rules_path):
                    success = False
            elif not self._download_rules(source_url, self.rules_path):
                success = False
        
        if success:
            self.logger.info("Toutes les règles Suricata ont été mises à jour avec succès.")
        else:
            self.log_error("Certaines mises à jour de règles Suricata ont échoué.")
        return success

    def run(self):
        """
        Boucle principale pour la mise à jour périodique des règles.
        """
        self.logger.info("Processus de gestion des règles Suricata démarré.")
        # Exécuter une première mise à jour au démarrage
        self.update_rules()

        while not self.is_shutdown_requested():
            self.logger.info(f"Prochaine vérification des règles Suricata dans {self.update_interval / 3600:.1f} heures.")
            time.sleep(self.update_interval)
            if self.is_shutdown_requested():
                break
            self.update_rules()
        self.logger.info("Processus de gestion des règles Suricata arrêté.")

# Exemple d'utilisation (pour les tests)
if __name__ == "__main__":
    from config_manager import ConfigManager
    import multiprocessing
    
    # Créer un fichier config.yaml temporaire pour le test
    temp_config_content = """
    suricata:
      rules_path: "temp_rules"
      oinkcode: "YOUR_OINKCODE" # Remplacez par un vrai oinkcode si vous testez ET Pro
      rule_sources:
        - "https://rules.emergingthreats.net/open/suricata-6.0.0/emerging.rules.tar.gz"
        # - "https://rules.emergingthreats.net/rules/etpro/oinkcode=YOUR_OINKCODE/etpro.rules.tar.gz" # Exemple ET Pro
      rules_update_interval_hours: 0.1 # Mettre à jour toutes les 6 minutes pour le test
    """
    with open('temp_config.yaml', 'w') as f:
        f.write(temp_config_content)

    try:
        config_mgr = ConfigManager(config_path='temp_config.yaml')
        manager = multiprocessing.Manager()
        shared_state = manager.dict({
            'last_error': ''
        })
        shutdown_event = multiprocessing.Event()

        rules_manager = SuricataRulesManager(shared_state, config_mgr, shutdown_event)
        
        process = multiprocessing.Process(target=rules_manager.run, name="SuricataRulesManagerProcess")
        process.start()
        
        print(f"Gestionnaire de règles Suricata démarré. Vérification des règles toutes les {rules_manager.update_interval / 3600:.1f} heures.")
        
        time.sleep(rules_manager.update_interval * 2 + 5) # Laisser le temps pour quelques mises à jour
        
        shutdown_event.set()
        process.join()

    except Exception as e:
        logging.error(f"Erreur lors du test de SuricataRulesManager: {e}")
    finally:
        if os.path.exists('temp_config.yaml'):
            os.remove('temp_config.yaml')
        if os.path.exists('temp_rules'):
            subprocess.run(["rm", "-rf", "temp_rules"], check=True, capture_output=True, text=True)
