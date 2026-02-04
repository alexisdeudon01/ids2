"""
Injection de dependances - conteneur DI avec punq.
"""

import logging
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path as _Path
from typing import Any, TypeVar

try:
    import punq
except ImportError as exc:  # pragma: no cover - runtime safeguard
    raise ImportError("punq n'est pas installe. Installez-le avec: pip install punq") from exc

# Import directly from modules to avoid circular import
from ..composants.connectivity import ConnectivityTester as ConnectivityChecker
from ..composants.docker_manager import DockerManager
from ..composants.metrics_server import MetricsCollector
from ..composants.resource_controller import ResourceController
from ..composants.vector_manager import VectorManager
from ..config.loader import ConfigManager
from ..domain import ConfigurationIDS
from ..infrastructure import AWSOpenSearchManager, InMemoryAlertStore, RedisClient
from ..interfaces import (
    AlerteSource,
    GestionnaireConfig,
    MetriquesProvider,
    PersistanceAlertes,
)
from ..suricata import SuricataManager
from .pipeline_status import (
    ComposantStatusProvider,
    PipelineStatusAggregator,
    PipelineStatusService,
    StaticStatusProvider,
)

T = TypeVar("T")
logger = logging.getLogger(__name__)


class ConteneurDI:
    """Conteneur d'injection de dependances."""

    def __init__(self) -> None:
        self._container = punq.Container()
        self._instances: dict[type, Any] = {}
        self._logger = logging.getLogger(__name__)

    def enregistrer_singleton(self, interface: type[T], instance: T) -> None:
        self._container.register(interface, instance=instance)
        self._instances[interface] = instance
        self._logger.debug("Singleton enregistre: %s", interface.__name__)

    def enregistrer_factory(self, interface: type[T], factory: Callable[..., T]) -> None:
        self._container.register(interface, factory=factory)
        self._logger.debug("Factory enregistree: %s", interface.__name__)

    def enregistrer_services(self, config_source: dict[str, Any] | str | _Path) -> None:
        self._logger.info("Enregistrement des services...")

        if isinstance(config_source, (str, _Path)):
            config_mgr = ConfigManager(str(config_source))
            config_dict = config_mgr.get_all()
        elif isinstance(config_source, dict):
            config_dict = config_source
            config_mgr = ConfigManager(config_dict)
        else:
            raise TypeError("config_source doit etre un dict ou un chemin")

        config = ConfigurationIDS(
            **{
                key: value
                for key, value in config_dict.items()
                if key in ConfigurationIDS.__dataclass_fields__
            }
        )
        self.enregistrer_singleton(ConfigurationIDS, config)
        self.enregistrer_singleton(GestionnaireConfig, config_mgr)

        suricata_mgr = SuricataManager(config_mgr)
        docker_mgr = DockerManager(config_mgr)
        vector_mgr = VectorManager(config_mgr)
        metrics_collector = MetricsCollector(config_mgr)
        resource_ctrl = ResourceController(config_mgr)
        connectivity = ConnectivityChecker(config_mgr)

        self.enregistrer_singleton(ResourceController, resource_ctrl)
        self.enregistrer_singleton(DockerManager, docker_mgr)
        self.enregistrer_singleton(VectorManager, vector_mgr)
        self.enregistrer_singleton(MetricsCollector, metrics_collector)
        self.enregistrer_singleton(ConnectivityChecker, connectivity)
        self.enregistrer_singleton(SuricataManager, suricata_mgr)
        self.enregistrer_singleton(AlerteSource, suricata_mgr)
        self.enregistrer_singleton(MetriquesProvider, metrics_collector)

        self.enregistrer_singleton(AWSOpenSearchManager, AWSOpenSearchManager(config_mgr))
        self.enregistrer_singleton(RedisClient, RedisClient(config_mgr))
        self.enregistrer_singleton(PersistanceAlertes, InMemoryAlertStore())

        providers = [
            StaticStatusProvider("ids2-network"),
            ComposantStatusProvider("ids2-agent", resource_ctrl),
            ComposantStatusProvider("suricata", suricata_mgr),
            ComposantStatusProvider("vector", vector_mgr),
            StaticStatusProvider("redis"),
            StaticStatusProvider("prometheus"),
            StaticStatusProvider("grafana"),
            StaticStatusProvider("fastapi"),
            StaticStatusProvider("cadvisor"),
            StaticStatusProvider("node_exporter"),
            StaticStatusProvider("opensearch"),
        ]
        pipeline_status = PipelineStatusAggregator(providers)
        pipeline_service = PipelineStatusService(pipeline_status)
        self.enregistrer_singleton(PipelineStatusAggregator, pipeline_status)
        self.enregistrer_singleton(PipelineStatusService, pipeline_service)

        self._logger.info("Services enregistres avec succes")

    def resoudre(self, service_type: type[T]) -> T:
        if service_type in self._instances:
            return self._instances[service_type]
        instance = self._container.resolve(service_type)
        self._logger.debug("Service resolu: %s", service_type.__name__)
        return instance

    @lru_cache(maxsize=128)
    def resoudre_en_cache(self, service_type: type[T]) -> T:
        return self.resoudre(service_type)


class ConteneurFactory:
    """Factory pour creer et configurer un conteneur DI."""

    @staticmethod
    def creer_conteneur_test() -> "ConteneurDI":
        return ConteneurDI()

    @staticmethod
    def creer_conteneur_prod(config_path: str) -> "ConteneurDI":
        container = ConteneurDI()
        container.enregistrer_services(config_path)
        return container


__all__ = ["ConteneurDI", "ConteneurFactory"]
