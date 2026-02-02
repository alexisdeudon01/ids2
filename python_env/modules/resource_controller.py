import psutil
import time
import multiprocessing
import logging
from base_component import BaseComponent # Import de BaseComponent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s')

class ResourceController(BaseComponent): # Hériter de BaseComponent
    """
    Contrôle et régule l'utilisation des ressources CPU et RAM.
    """
    def __init__(self, shared_state, config_manager, shutdown_event=None):
        super().__init__(shared_state, config_manager, shutdown_event) # Appel du constructeur parent
        self.cpu_limit = self.get_config('raspberry_pi.cpu_limit_percent', 70)
        self.ram_limit = self.get_config('raspberry_pi.ram_limit_percent', 70)
        self.sleep_interval = self.get_config('resource_controller.check_interval', 1) # Rendre configurable
        # Utiliser shared_state pour throttling_level pour la cohérence
        # self.throttling_level = multiprocessing.Value('i', 0) # Supprimé

    def _get_system_metrics(self):
        """
        Récupère l'utilisation actuelle du CPU et de la RAM.
        """
        cpu_percent = psutil.cpu_percent(interval=None) # Non-bloquant
        ram_percent = psutil.virtual_memory().percent
        return cpu_percent, ram_percent

    def _apply_throttling(self, cpu_usage, ram_usage):
        """
        Applique une stratégie de régulation basée sur l'utilisation des ressources.
        Met à jour le niveau de régulation dans l'état partagé.
        """
        current_throttling_level = 0
        # Rendre les seuils configurables
        cpu_limit_high = self.get_config('raspberry_pi.cpu_limit_high_percent', self.cpu_limit + 10)
        ram_limit_high = self.get_config('raspberry_pi.ram_limit_high_percent', self.ram_limit + 10)
        cpu_limit_medium = self.get_config('raspberry_pi.cpu_limit_medium_percent', self.cpu_limit + 5)
        ram_limit_medium = self.get_config('raspberry_pi.ram_limit_medium_percent', self.ram_limit + 5)

        if cpu_usage > self.cpu_limit or ram_usage > self.ram_limit:
            if cpu_usage > cpu_limit_high or ram_usage > ram_limit_high:
                current_throttling_level = 3 # Sévère
            elif cpu_usage > cpu_limit_medium or ram_usage > ram_limit_medium:
                current_throttling_level = 2 # Modéré
            else:
                current_throttling_level = 1 # Léger
        
        # Utiliser la méthode de la classe de base pour mettre à jour l'état partagé
        self.update_shared_state('throttling_level', current_throttling_level)

        if current_throttling_level > 0:
            self.logger.warning(f"Régulation activée : niveau {current_throttling_level}. CPU: {cpu_usage:.2f}%, RAM: {ram_usage:.2f}%")
        else:
            self.logger.info(f"Régulation désactivée. CPU: {cpu_usage:.2f}%, RAM: {ram_usage:.2f}%")

    def run(self):
        """
        Boucle principale du contrôleur de ressources.
        """
        self.logger.info("Processus de Contrôle / Ressources démarré.")
        while not self.is_shutdown_requested(): # Utiliser l'événement d'arrêt
            cpu_usage, ram_usage = self._get_system_metrics()

            self.update_shared_state('cpu_usage', cpu_usage)
            self.update_shared_state('ram_usage', ram_usage)

            self._apply_throttling(cpu_usage, ram_usage)

            time.sleep(self.sleep_interval)
        self.logger.info("Processus de Contrôle / Ressources arrêté.")

# Exemple d'utilisation (pour les tests)
if __name__ == "__main__":
    import os
    from config_manager import ConfigManager
    
    # Créer un fichier config.yaml temporaire pour le test
    temp_config_content = """
    raspberry_pi:
      cpu_limit_percent: 70
      ram_limit_percent: 70
      cpu_limit_medium_percent: 75
      ram_limit_medium_percent: 75
      cpu_limit_high_percent: 80
      ram_limit_high_percent: 80
    resource_controller:
      check_interval: 1
    """
    with open('temp_config.yaml', 'w') as f:
        f.write(temp_config_content)

    try:
        config_mgr = ConfigManager(config_path='temp_config.yaml')
        manager = multiprocessing.Manager()
        shared_state = manager.dict({
            'cpu_usage': 0.0,
            'ram_usage': 0.0,
            'throttling_level': 0,
            'last_error': '' # Ajout pour BaseComponent
        })
        shutdown_event = multiprocessing.Event()

        controller = ResourceController(shared_state, config_mgr, shutdown_event)
        
        # Simuler une exécution pendant quelques secondes
        process = multiprocessing.Process(target=controller.run, name="ResourceControllerProcess")
        process.start()
        
        for _ in range(5): # Réduire le nombre d'itérations pour le test
            time.sleep(2)
            print(f"État partagé - CPU: {shared_state['cpu_usage']:.2f}%, RAM: {shared_state['ram_usage']:.2f}%, Throttling: {shared_state['throttling_level']}")
        
        shutdown_event.set() # Demander l'arrêt
        process.join()

    except Exception as e:
        logging.error(f"Erreur lors du test du ResourceController: {e}")
    finally:
        if os.path.exists('temp_config.yaml'):
            os.remove('temp_config.yaml')
