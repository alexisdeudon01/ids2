"""
Injection de dependances - conteneur DI avec punq.
"""

from collections.abc import Callable
from functools import lru_cache
import logging
from pathlib import Path as _Path
from typing import Any, TypeVar

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

try:
    import punq
except ImportError as exc:  # pragma: no cover - runtime safeguard
    raise ImportError("punq n'est pas installe. Installez-le avec: pip install punq") from exc

# Import directly from modules to avoid circular import


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
        
        config_mgr = self._setup_config(config_source)
        self._register_core_services(config_mgr)
        self._register_infrastructure_services(config_mgr)
        self._register_pipeline_services()
        
        self._logger.info("Services enregistres avec succes")

    def _setup_config(self, config_source: dict[str, Any] | str | _Path) -> ConfigManager:
        if isinstance(config_source, (str, _Path)):
            config_mgr = ConfigManager(str(config_source))
            config_dict = config_mgr.get_all()
        elif isinstance(config_source, dict):
            config_dict = config_source
            config_mgr = ConfigManager(config_dict)
        else:
            raise TypeError("config_source doit etre un dict ou un chemin")

        config = ConfigurationIDS(
            **{k: v for k, v in config_dict.items() if k in ConfigurationIDS.__dataclass_fields__}
        )
        self.enregistrer_singleton(ConfigurationIDS, config)
        self.enregistrer_singleton(GestionnaireConfig, config_mgr)
        return config_mgr

    def _register_core_services(self, config_mgr: ConfigManager) -> None:
        services = {
            ResourceController: ResourceController(config_mgr),
            DockerManager: DockerManager(config_mgr),
            VectorManager: VectorManager(config_mgr),
            MetricsCollector: MetricsCollector(config_mgr),
            ConnectivityChecker: ConnectivityChecker(config_mgr),
            SuricataManager: SuricataManager(config_mgr),
        }
        
        for service_type, instance in services.items():
            self.enregistrer_singleton(service_type, instance)
        
        self.enregistrer_singleton(AlerteSource, services[SuricataManager])
        self.enregistrer_singleton(MetriquesProvider, services[MetricsCollector])

    def _register_infrastructure_services(self, config_mgr: ConfigManager) -> None:
        self.enregistrer_singleton(AWSOpenSearchManager, AWSOpenSearchManager(config_mgr))
        self.enregistrer_singleton(RedisClient, RedisClient(config_mgr))
        self.enregistrer_singleton(PersistanceAlertes, InMemoryAlertStore())

    def _register_pipeline_services(self) -> None:
        resource_ctrl = self.resoudre(ResourceController)
        suricata_mgr = self.resoudre(SuricataManager)
        vector_mgr = self.resoudre(VectorManager)
        
        providers = [
            StaticStatusProvider("ids2-network"),
            ComposantStatusProvider("ids2-agent", resource_ctrl),
            ComposantStatusProvider("suricata", suricata_mgr),
            ComposantStatusProvider("vector", vector_mgr),
            *[StaticStatusProvider(name) for name in [
                "redis", "prometheus", "grafana", "fastapi", 
                "cadvisor", "node_exporter", "opensearch"
            ]]
        ]
        
        pipeline_status = PipelineStatusAggregator(providers)
        pipeline_service = PipelineStatusService(pipeline_status)
        self.enregistrer_singleton(PipelineStatusAggregator, pipeline_status)
        self.enregistrer_singleton(PipelineStatusService, pipeline_service)

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