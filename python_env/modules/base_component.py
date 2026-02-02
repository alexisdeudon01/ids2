import logging

class BaseComponent:
    """
    Classe de base pour les composants de l'agent, fournissant un accès
    standardisé à l'état partagé et au gestionnaire de configuration.
    """
    def __init__(self, shared_state, config_manager, shutdown_event=None):
        self.shared_state = shared_state
        self.config = config_manager
        self.shutdown_event = shutdown_event
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        # Configurer le handler si ce n'est pas déjà fait par basicConfig
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def get_config(self, key, default=None):
        """
        Récupère une valeur de configuration avec une clé et une valeur par défaut.
        """
        return self.config.get(key, default)

    def update_shared_state(self, key, value):
        """
        Met à jour une valeur dans l'état partagé.
        """
        self.shared_state[key] = value
        self.logger.debug(f"État partagé mis à jour : {key} = {value}")

    def log_error(self, message, exception=None):
        """
        Loggue une erreur et met à jour l'état partagé avec le dernier message d'erreur.
        """
        full_message = message
        if exception:
            full_message = f"{message}: {exception}"
            self.logger.exception(full_message)
        else:
            self.logger.error(full_message)
        self.update_shared_state('last_error', full_message)

    def is_shutdown_requested(self):
        """
        Vérifie si un arrêt a été demandé.
        """
        return self.shutdown_event and self.shutdown_event.is_set()

    def run(self):
        """
        Méthode principale à implémenter par les classes dérivées.
        """
        raise NotImplementedError("La méthode 'run' doit être implémentée par les classes dérivées.")
