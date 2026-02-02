from prometheus_client import start_http_server, Gauge, Counter
import time
import logging
import multiprocessing
from base_component import BaseComponent # Import de BaseComponent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s')

class MetricsServer(BaseComponent): # Hériter de BaseComponent
    """
    Expose les métriques du pipeline via un serveur HTTP Prometheus.
    """
    def __init__(self, shared_state, config_manager, shutdown_event=None): # Ajuster l'ordre des arguments
        super().__init__(shared_state, config_manager, shutdown_event) # Appel du constructeur parent
        self.port = self.get_config('prometheus.port', 9100)
        self.update_interval = self.get_config('prometheus.update_interval', 5) # Rendre configurable

        # Définition des métriques Prometheus
        self.cpu_usage_gauge = Gauge('ids2_cpu_usage_percent', 'Utilisation CPU du Raspberry Pi en pourcentage')
        self.ram_usage_gauge = Gauge('ids2_ram_usage_percent', 'Utilisation RAM du Raspberry Pi en pourcentage')
        self.redis_queue_depth_gauge = Gauge('ids2_redis_queue_depth', 'Profondeur de la file d\'attente Redis')
        self.vector_health_gauge = Gauge('ids2_vector_health', 'État de santé de Vector (1=sain, 0=non sain)')
        self.ingestion_rate_counter = Counter('ids2_ingestion_rate_total', 'Nombre total de logs ingérés')
        self.error_counter = Counter('ids2_error_total', 'Nombre total d\'erreurs rencontrées')
        self.aws_ready_gauge = Gauge('ids2_aws_ready', 'État de préparation AWS (1=prêt, 0=non prêt)')
        self.redis_ready_gauge = Gauge('ids2_redis_ready', 'État de préparation Redis (1=prêt, 0=non prêt)')
        self.pipeline_ok_gauge = Gauge('ids2_pipeline_ok', 'État global du pipeline (1=OK, 0=problème)')
        self.throttling_level_gauge = Gauge('ids2_throttling_level', 'Niveau de régulation du pipeline (0=normal, 3=sévère)')


    def _update_metrics(self):
        """
        Met à jour les métriques Prometheus à partir de l'état partagé.
        """
        self.cpu_usage_gauge.set(self.shared_state.get('cpu_usage', 0.0))
        self.ram_usage_gauge.set(self.shared_state.get('ram_usage', 0.0))
        self.redis_queue_depth_gauge.set(self.shared_state.get('redis_queue_depth', 0))
        self.vector_health_gauge.set(1 if self.shared_state.get('vector_healthy', False) else 0)
        
        # Incrémenter les compteurs si des incréments sont signalés
        ingestion_increment = self.shared_state.get('ingestion_rate_increment', 0)
        if ingestion_increment > 0:
            self.ingestion_rate_counter.inc(ingestion_increment)
            self.update_shared_state('ingestion_rate_increment', 0) # Réinitialiser après utilisation

        error_increment = self.shared_state.get('error_increment', 0)
        if error_increment > 0:
            self.error_counter.inc(error_increment)
            self.update_shared_state('error_increment', 0) # Réinitialiser après utilisation

        self.aws_ready_gauge.set(1 if self.shared_state.get('aws_ready', False) else 0)
        self.redis_ready_gauge.set(1 if self.shared_state.get('redis_ready', False) else 0)
        self.pipeline_ok_gauge.set(1 if self.shared_state.get('pipeline_ok', False) else 0)
        self.throttling_level_gauge.set(self.shared_state.get('throttling_level', 0))


    def run(self):
        """
        Démarre le serveur HTTP Prometheus et met à jour les métriques.
        """
        self.logger.info(f"Processus de Surveillance / Métriques démarré sur le port {self.port}.")
        start_http_server(self.port)
        while not self.is_shutdown_requested(): # Utiliser l'événement d'arrêt
            self._update_metrics()
            time.sleep(self.update_interval)
        self.logger.info("Processus de Surveillance / Métriques arrêté.")

# Exemple d'utilisation (pour les tests)
if __name__ == "__main__":
    from config_manager import ConfigManager
    import os
    
    # Créer un fichier config.yaml temporaire pour le test
    temp_config_content = """
    prometheus:
      port: 9100
      update_interval: 2
    """
    with open('temp_config.yaml', 'w') as f:
        f.write(temp_config_content)

    try:
        config_mgr = ConfigManager(config_path='temp_config.yaml')
        manager = multiprocessing.Manager()
        shared_state = manager.dict({
            'cpu_usage': 15.5,
            'ram_usage': 30.2,
            'redis_queue_depth': 150,
            'vector_healthy': True,
            'aws_ready': True,
            'redis_ready': True,
            'pipeline_ok': True,
            'throttling_level': 0,
            'last_error': '',
            'ingestion_rate_increment': 0,
            'error_increment': 0
        })
        shutdown_event = multiprocessing.Event()

        metrics_server = MetricsServer(shared_state, config_mgr, shutdown_event)
        
        process = multiprocessing.Process(target=metrics_server.run, name="MetricsServerProcess")
        process.start()
        
        print(f"Serveur Prometheus démarré sur le port {metrics_server.port}. Accédez à http://localhost:{metrics_server.port}/metrics")
        print("Mise à jour des métriques dans l'état partagé...")
        
        for i in range(3):
            time.sleep(metrics_server.update_interval + 1)
            # Assurez-vous que les valeurs sont des nombres avant d'effectuer des opérations arithmétiques
            shared_state['cpu_usage'] = float(shared_state.get('cpu_usage', 0.0)) + 5.0
            shared_state['ram_usage'] = float(shared_state.get('ram_usage', 0.0)) + 10.0
            shared_state['redis_queue_depth'] = int(shared_state.get('redis_queue_depth', 0)) + 50
            shared_state['ingestion_rate_increment'] = int(shared_state.get('ingestion_rate_increment', 0)) + 10 # Simuler l'ingestion
            if i == 1:
                shared_state['vector_healthy'] = False
                shared_state['pipeline_ok'] = False
                shared_state['throttling_level'] = 2
                shared_state['error_increment'] = int(shared_state.get('error_increment', 0)) + 1 # Simuler une erreur
                shared_state['last_error'] = "Vector down"
            print(f"État partagé mis à jour (itération {i+1}).")
        
        shutdown_event.set()
        process.join()

    except Exception as e:
        logging.error(f"Erreur lors du test de MetricsServer: {e}")
    finally:
        if os.path.exists('temp_config.yaml'):
            os.remove('temp_config.yaml')
