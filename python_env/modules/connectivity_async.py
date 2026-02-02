import asyncio
import uvloop
import socket
import ssl
import time
import logging
import aiohttp
from urllib.parse import urlparse # Import pour l'analyse d'URL
from base_component import BaseComponent # Import de BaseComponent
from aws_manager import AWSManager # Pour l'authentification SigV4

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s')

class ConnectivityAsync(BaseComponent): # Hériter de BaseComponent
    """
    Gère les vérifications de connectivité réseau asynchrones (DNS, TLS, OpenSearch).
    """
    def __init__(self, shared_state, config_manager, shutdown_event=None):
        super().__init__(shared_state, config_manager, shutdown_event) # Appel du constructeur parent
        self.opensearch_endpoint = self.get_config('aws.opensearch_endpoint')
        self.aws_region = self.get_config('aws.region')
        self.redis_host = self.get_config('redis.host')
        self.redis_port = self.get_config('redis.port')
        self.max_retries = self.get_config('connectivity.max_retries', 5) # Rendre configurable
        self.initial_backoff = self.get_config('connectivity.initial_backoff', 1) # Rendre configurable

        # Configurer uvloop comme boucle d'événements par défaut
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

        # Initialiser AWSManager pour l'authentification SigV4
        self.aws_manager = AWSManager(config_manager, shared_state)

    async def _retry_operation(self, func, *args, **kwargs):
        """
        Exécute une fonction avec réessais et backoff exponentiel.
        """
        retries = 0
        while retries < self.max_retries:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                retries += 1
                if retries >= self.max_retries:
                    self.log_error(f"Opération '{func.__name__}' échouée après {self.max_retries} tentatives", e)
                    raise
                sleep_time = self.initial_backoff * (2 ** retries)
                self.logger.warning(f"Opération '{func.__name__}' échouée ({e}). Réessai dans {sleep_time:.2f}s (tentative {retries}/{self.max_retries}).")
                await asyncio.sleep(sleep_time)

    async def check_dns_resolution(self, hostname):
        """
        Vérifie la résolution DNS d'un hostname.
        """
        try:
            await asyncio.get_event_loop().getaddrinfo(hostname, None)
            self.logger.info(f"Résolution DNS réussie pour {hostname}")
            return True
        except socket.gaierror as e:
            self.log_error(f"Échec de la résolution DNS pour {hostname}", e)
            raise

    async def check_tls_handshake(self, hostname, port=443):
        """
        Vérifie la négociation TLS avec un hôte.
        """
        writer = None
        try:
            ssl_context = ssl.create_default_context()
            reader, writer = await asyncio.open_connection(hostname, port, ssl=ssl_context)
            self.logger.info(f"Négociation TLS réussie avec {hostname}:{port}")
            return True
        except (ConnectionRefusedError, socket.timeout, ssl.SSLError, OSError) as e:
            self.log_error(f"Échec de la négociation TLS avec {hostname}:{port}", e)
            raise
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()

    async def check_opensearch_bulk_test(self):
        """
        Effectue un test de connectivité à l'API _bulk d'OpenSearch avec authentification SigV4.
        """
        if not self.opensearch_endpoint:
            self.logger.warning("Endpoint OpenSearch non configuré, impossible de tester la connectivité.")
            self.update_shared_state('aws_ready', False)
            return False

        try:
            # Utiliser AWSManager pour obtenir le client OpenSearch authentifié
            client = self.aws_manager._get_opensearch_client() # Accéder à la méthode interne pour le client

            # Utiliser une API légère pour le test, par exemple _cluster/health
            response = await asyncio.to_thread(client.cluster.health, wait_for_status='yellow', timeout='5s')
            
            if response and response.get('status') in ['green', 'yellow']:
                self.logger.info(f"Test OpenSearch réussi. Statut: {response.get('status')}")
                self.update_shared_state('aws_ready', True)
                return True
            else:
                self.logger.warning(f"Test OpenSearch échoué. Statut: {response.get('status')}")
                self.update_shared_state('aws_ready', False)
                self.log_error(f"OpenSearch health check failed: {response.get('status')}")
                return False
        except Exception as e:
            self.log_error(f"Erreur lors du test OpenSearch", e)
            self.update_shared_state('aws_ready', False)
            raise

    async def check_redis_connectivity(self):
        """
        Vérifie la connectivité à Redis.
        """
        writer = None
        try:
            reader, writer = await asyncio.open_connection(self.redis_host, self.redis_port)
            self.logger.info(f"Connectivité Redis réussie à {self.redis_host}:{self.redis_port}")
            self.update_shared_state('redis_ready', True)
            return True
        except (ConnectionRefusedError, socket.timeout, OSError) as e:
            self.log_error(f"Échec de la connectivité Redis à {self.redis_host}:{self.redis_port}", e)
            self.update_shared_state('redis_ready', False)
            raise
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()

    async def run_connectivity_checks(self):
        """
        Exécute toutes les vérifications de connectivité en parallèle.
        """
        self.logger.info("Processus de Connectivité (ASYNC) démarré.")
        while not self.is_shutdown_requested():
            try:
                opensearch_hostname = None
                if self.opensearch_endpoint:
                    parsed_url = urlparse(self.opensearch_endpoint)
                    opensearch_hostname = parsed_url.hostname

                tasks = []
                if opensearch_hostname:
                    tasks.append(self._retry_operation(self.check_dns_resolution, opensearch_hostname))
                    tasks.append(self._retry_operation(self.check_tls_handshake, opensearch_hostname))
                    tasks.append(self._retry_operation(self.check_opensearch_bulk_test))
                
                tasks.append(self._retry_operation(self.check_redis_connectivity))

                results = await asyncio.gather(*tasks, return_exceptions=True)

                pipeline_ok = all(r is True for r in results if not isinstance(r, Exception))
                self.update_shared_state('pipeline_ok', pipeline_ok)
                if not pipeline_ok:
                    self.logger.warning("Certaines vérifications de connectivité ont échoué.")
                else:
                    self.logger.info("Toutes les vérifications de connectivité sont OK.")

            except Exception as e:
                self.log_error(f"Erreur critique dans le processus de connectivité", e)
                self.update_shared_state('pipeline_ok', False)
            
            interval = self.get_config('connectivity.check_interval', 10)
            if not isinstance(interval, (int, float)):
                self.logger.warning(f"connectivity.check_interval dans config.yaml n'est pas un nombre. Utilisation de la valeur par défaut (10s).")
                interval = 10
            await asyncio.sleep(interval)
        self.logger.info("Processus de Connectivité (ASYNC) arrêté.")

    def run(self):
        """
        Point d'entrée pour le processus de connectivité.
        """
        asyncio.run(self.run_connectivity_checks())

# Exemple d'utilisation (pour les tests)
if __name__ == "__main__":
    import os
    from config_manager import ConfigManager
    import multiprocessing

    # Créer un fichier config.yaml temporaire pour le test
    temp_config_content = """
    aws:
      opensearch_endpoint: "https://your-opensearch-domain.eu-west-1.es.amazonaws.com" # Remplacez par un endpoint valide ou invalide pour tester
      region: "eu-west-1"
      profile: "moi33" # Assurez-vous que ce profil est configuré localement pour les tests réels
    redis:
      host: "localhost"
      port: 6379
    connectivity:
      check_interval: 5
      max_retries: 3
      initial_backoff: 1
    """
    with open('temp_config.yaml', 'w') as f:
        f.write(temp_config_content)

    try:
        config_mgr = ConfigManager(config_path='temp_config.yaml')
        manager = multiprocessing.Manager()
        shared_state = manager.dict({
            'aws_ready': False,
            'redis_ready': False,
            'pipeline_ok': False,
            'last_error': ''
        })
        shutdown_event = multiprocessing.Event()

        connectivity_checker = ConnectivityAsync(shared_state, config_mgr, shutdown_event)
        
        process = multiprocessing.Process(target=connectivity_checker.run, name="ConnectivityProcess")
        process.start()
        
        for _ in range(3):
            time.sleep(connectivity_checker.get_config('connectivity.check_interval', 5) + 1)
            print(f"\nÉtat partagé - AWS Ready: {shared_state['aws_ready']}, Redis Ready: {shared_state['redis_ready']}, Pipeline OK: {shared_state['pipeline_ok']}, Last Error: {shared_state['last_error']}")
        
        shutdown_event.set()
        process.join()

    except Exception as e:
        logging.error(f"Erreur lors du test de ConnectivityAsync: {e}")
    finally:
        if os.path.exists('temp_config.yaml'):
            os.remove('temp_config.yaml')
