import subprocess
import logging
import os
from base_component import BaseComponent # Import de BaseComponent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s')

class GitWorkflow(BaseComponent): # Hériter de BaseComponent
    """
    Gère les opérations Git pour le dépôt du projet.
    """
    def __init__(self, shared_state, config_manager, shutdown_event=None): # Ajuster l'ordre des arguments
        super().__init__(shared_state, config_manager, shutdown_event) # Appel du constructeur parent
        self.target_branch = self.get_config('git.branch', 'dev')

    def _run_git_command(self, command_args):
        """
        Exécute une commande Git et gère les erreurs.
        """
        cmd = ["git"] + command_args
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            if result.stdout:
                self.logger.info(f"Sortie Git : {result.stdout.strip()}")
            if result.stderr:
                self.logger.warning(f"Erreurs/Avertissements Git : {result.stderr.strip()}")
            return True
        except subprocess.CalledProcessError as e:
            self.log_error(f"Échec de la commande Git '{' '.join(cmd)}' : {e.stderr.strip()}", e)
            return False
        except FileNotFoundError:
            self.log_error("La commande 'git' n'a pas été trouvée. Assurez-vous que Git est installé.")
            return False
        except Exception as e:
            self.log_error(f"Erreur inattendue lors de l'exécution de Git", e)
            return False

    def check_branch(self):
        """
        Vérifie si la branche actuelle est la branche cible.
        """
        self.logger.info(f"Vérification de la branche Git actuelle. Branche cible : '{self.target_branch}'")
        try:
            result = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], check=True, capture_output=True, text=True)
            current_branch = result.stdout.strip()
            if current_branch == self.target_branch:
                self.logger.info(f"La branche actuelle est '{current_branch}', ce qui correspond à la branche cible.")
                return True
            else:
                self.log_error(f"La branche actuelle est '{current_branch}', mais la branche cible est '{self.target_branch}'.")
                return False
        except subprocess.CalledProcessError as e:
            self.log_error(f"Impossible de déterminer la branche Git actuelle : {e.stderr.strip()}", e)
            return False

    def commit_and_push_changes(self, message="chore(dev): agent bootstrap/update"):
        """
        Ajoute, committe et pousse les changements vers la branche cible.
        """
        self.logger.info("Ajout de tous les fichiers modifiés/nouveaux à Git.")
        if not self._run_git_command(["add", "-A"]):
            return False
        
        self.logger.info(f"Création du commit avec le message : '{message}'")
        # Tenter le commit et vérifier si l'erreur est "nothing to commit"
        try:
            subprocess.run(["git", "commit", "-m", message], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            if "nothing to commit" in e.stderr.lower():
                self.logger.info("Aucun changement à committer.")
                return True # Considérer comme un succès si rien à committer
            else:
                self.log_error(f"Échec du commit Git : {e.stderr.strip()}", e)
                return False
        except Exception as e:
            self.log_error(f"Erreur inattendue lors du commit Git", e)
            return False
        
        self.logger.info(f"Push des changements vers 'origin/{self.target_branch}'")
        if not self._run_git_command(["push", "origin", self.target_branch]):
            return False
        
        self.logger.info("Changements Git poussés avec succès.")
        return True

# Exemple d'utilisation (pour les tests)
if __name__ == "__main__":
    from config_manager import ConfigManager
    import multiprocessing
    
    # Créer un fichier config.yaml temporaire pour le test
    temp_config_content = """
    git:
      branch: "dev"
    """
    with open('temp_config.yaml', 'w') as f:
        f.write(temp_config_content)

    # Initialiser un dépôt Git temporaire pour le test
    os.makedirs('temp_repo', exist_ok=True)
    os.chdir('temp_repo')
    subprocess.run(["git", "init"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "checkout", "-b", "dev"], check=True, capture_output=True, text=True)
    with open('test_file.txt', 'w') as f:
        f.write("Initial content")
    subprocess.run(["git", "add", "test_file.txt"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], check=True, capture_output=True, text=True)
    # Simuler une remote
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/test/test.git"], check=True, capture_output=True, text=True)


    try:
        config_mgr = ConfigManager(config_path='../temp_config.yaml')
        manager = multiprocessing.Manager()
        shared_state = manager.dict({
            'last_error': ''
        })
        shutdown_event = multiprocessing.Event()

        git_workflow = GitWorkflow(shared_state, config_mgr, shutdown_event)

        print("\nTest de vérification de la branche...")
        print(f"Branche correcte : {git_workflow.check_branch()}")

        print("\nModification d'un fichier et test de commit/push...")
        with open('test_file.txt', 'a') as f:
            f.write("\nAdded new line.")
        
        print(f"Commit et push réussis (le push échouera pour le test) : {git_workflow.commit_and_push_changes()}")

    except Exception as e:
        logging.error(f"Erreur lors du test de GitWorkflow: {e}")
    finally:
        os.chdir('..')
        if os.path.exists('temp_config.yaml'):
            os.remove('temp_config.yaml')
        if os.path.exists('temp_repo'):
            subprocess.run(["rm", "-rf", "temp_repo"], check=True, capture_output=True, text=True)
