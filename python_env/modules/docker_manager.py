import docker
import logging
import time
import os
import subprocess
from docker.errors import NotFound # Import spécifique de NotFound
from base_component import BaseComponent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s')

class DockerManager(BaseComponent):
    """
    Gère le cycle de vie des conteneurs Docker et Docker Compose.
    """
    def __init__(self, shared_state, config_manager, shutdown_event=None):
        super().__init__(shared_state, config_manager, shutdown_event)
        self.docker_compose_path = self.get_config('docker.compose_file', 'docker/docker-compose.yml')
        self.client = docker.from_env()
        self.required_services = self.get_config('docker.required_services', ["vector", "redis", "prometheus", "grafana"])

    def _check_docker_daemon(self):
        """
        Vérifie si le démon Docker est en cours d'exécution.
        """
        try:
            self.client.ping()
            self.logger.info("Le démon Docker est en cours d'exécution.")
            return True
        except Exception as e:
            self.log_error(f"Le démon Docker n'est pas accessible", e)
            return False

    def _run_docker_compose_command(self, command, detach=False):
        """
        Exécute une commande docker compose.
        """
        if not os.path.exists(self.docker_compose_path):
            self.log_error(f"Fichier docker-compose.yml non trouvé à : {self.docker_compose_path}")
            return False

        # Utiliser 'docker compose' (nouvelle syntaxe)
        cmd = ["docker", "compose", "-f", self.docker_compose_path, command]
        if detach:
            cmd.append("-d")
        
        self.logger.info(f"Exécution de la commande Docker Compose : {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            self.logger.info(f"Sortie Docker Compose :\n{result.stdout}")
            if result.stderr:
                self.logger.warning(f"Erreurs/Avertissements Docker Compose :\n{result.stderr}")
            return True
        except subprocess.CalledProcessError as e:
            self.log_error(f"Échec de la commande Docker Compose '{command}' : {e.stderr.strip()}", e)
            return False
        except FileNotFoundError:
            self.log_error("La commande 'docker compose' n'a pas été trouvée. Assurez-vous que Docker Compose est installé et dans le PATH.")
            return False
        except Exception as e:
            self.log_error(f"Erreur inattendue lors de l'exécution de Docker Compose", e)
            return False

    def prepare_docker_stack(self):
        """
        Construit et démarre la pile Docker Compose.
        """
        if not self._check_docker_daemon():
            return False
        
        self.logger.info("Préparation de la pile Docker...")
        if not self._run_docker_compose_command("build"):
            return False
        if not self._run_docker_compose_command("up", detach=True):
            return False
        
        self.logger.info("Pile Docker démarrée avec succès.")
        return True

    def stop_docker_stack(self):
        """
        Arrête et supprime la pile Docker Compose.
        """
        if not self._check_docker_daemon():
            return False
        
        self.logger.info("Arrêt de la pile Docker...")
        if not self._run_docker_compose_command("down"):
            return False
        
        self.logger.info("Pile Docker arrêtée et supprimée.")
        return True

    def check_stack_health(self):
        """
        Vérifie la santé des services Docker en utilisant les Healthchecks si disponibles.
        """
        if not self._check_docker_daemon():
            return False
        
        all_healthy = True
        for service_name in self.required_services:
            try:
                # Tenter d'obtenir le conteneur par son nom de service Docker Compose
                # Le nom réel du conteneur peut varier, mais 'docker compose ps -q <service_name>' est plus fiable
                result = subprocess.run(
                    ["docker", "compose", "-f", self.docker_compose_path, "ps", "-q", service_name],
                    check=True, capture_output=True, text=True
                )
                container_id = result.stdout.strip()

                if not container_id:
                    self.logger.warning(f"Le conteneur pour le service Docker '{service_name}' n'a pas été trouvé.")
                    all_healthy = False
                    break

                container = self.client.containers.get(container_id)
                
                # Vérifier le statut du conteneur
                if container.status != 'running':
                    self.logger.warning(f"Le service Docker '{service_name}' n'est pas en cours d'exécution. Statut: {container.status}")
                    all_healthy = False
                    break
                
                # Vérifier le Healthcheck si défini
                container_info = self.client.api.inspect_container(container_id)
                health_status = container_info.get('State', {}).get('Health', {}).get('Status')

                if health_status and health_status != 'healthy':
                    self.logger.warning(f"Le service Docker '{service_name}' n'est pas sain. Statut de santé: {health_status}")
                    all_healthy = False
                    break
                elif health_status == 'healthy':
                    self.logger.info(f"Le service Docker '{service_name}' est sain.")
                else:
                    self.logger.info(f"Le service Docker '{service_name}' est en cours d'exécution (pas de Healthcheck défini ou non disponible).")

            except docker.errors.NotFound:
                self.logger.warning(f"Le conteneur pour le service Docker '{service_name}' n'a pas été trouvé.")
                all_healthy = False
                break
            except subprocess.CalledProcessError as e:
                self.log_error(f"Erreur lors de la récupération de l'ID du conteneur pour '{service_name}' : {e.stderr.strip()}", e)
                all_healthy = False
                break
            except Exception as e:
                self.log_error(f"Erreur lors de la vérification du service Docker '{service_name}'", e)
                all_healthy = False
                break
        
        self.update_shared_state('docker_healthy', all_healthy)
        if not all_healthy:
            self.log_error("La pile Docker n'est pas saine.")
        return all_healthy

# Exemple d'utilisation (pour les tests)
if __name__ == "__main__":
    from config_manager import ConfigManager
    import multiprocessing
    
    # Créer un fichier config.yaml temporaire pour le test
    temp_config_content = """
    docker:
      compose_file: "docker/docker-compose.yml"
      required_services: ["test_service"]
      vector_cpu: 1.0
      vector_ram_mb: 1024
      redis_cpu: 0.5
      redis_ram_mb: 512
      prometheus_cpu: 0.5
      prometheus_ram_mb: 512
      grafana_cpu: 0.5
      grafana_ram_mb: 512
    """
    with open('temp_config.yaml', 'w') as f:
        f.write(temp_config_content)

    # Créer un docker-compose.yml temporaire pour le test
    temp_docker_compose_content = """
version: '3.8'
services:
  test_service:
    image: alpine/git
    command: ["sh", "-c", "echo 'Hello from Docker!' && sleep 30"]
    healthcheck:
      test: ["CMD", "echo", "healthy"]
      interval: 5s
      timeout: 1s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '0.1'
          memory: 64M
"""
    os.makedirs('docker', exist_ok=True)
    with open('docker/docker-compose.yml', 'w') as f:
        f.write(temp_docker_compose_content)

    try:
        config_mgr = ConfigManager(config_path='temp_config.yaml')
        manager = multiprocessing.Manager()
        shared_state = manager.dict({
            'docker_healthy': False,
            'last_error': ''
        })
        shutdown_event = multiprocessing.Event()

        docker_mgr = DockerManager(shared_state, config_mgr, shutdown_event)

        print("\nTest de préparation de la pile Docker...")
        if docker_mgr.prepare_docker_stack():
            print("Pile Docker préparée. Attente de 10 secondes pour la santé...")
            time.sleep(10) # Laisser le temps au healthcheck de s'exécuter
            print(f"Santé de la pile Docker : {docker_mgr.check_stack_health()}")
        
        print("\nTest d'arrêt de la pile Docker...")
        docker_mgr.stop_docker_stack()

    except Exception as e:
        logging.error(f"Erreur lors du test de DockerManager: {e}")
    finally:
        if os.path.exists('temp_config.yaml'):
            os.remove('temp_config.yaml')
        if os.path.exists('docker/docker-compose.yml'):
            os.remove('docker/docker-compose.yml')
        if os.path.exists('docker'):
            subprocess.run(["rm", "-rf", "docker"], check=True, capture_output=True, text=True) # Utiliser rm -rf pour supprimer le répertoire non vide
