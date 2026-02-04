"""Package app - Orchestration et conteneur DI."""

from .decorateurs import cache_resultat, log_appel, metriques, retry

# Lazy imports to avoid circular dependencies
# ConteneurDI and ConteneurFactory should be imported from ids.app.container directly
# AgentSupervisor and main should be imported from ids.app.supervisor directly

__all__ = [
    "cache_resultat",
    "log_appel",
    "metriques",
    "retry",
]


def __getattr__(name: str):
    """Lazy loading for components with circular import issues."""
    if name in ("ConteneurDI", "ConteneurFactory"):
        from .container import ConteneurDI, ConteneurFactory

        return ConteneurDI if name == "ConteneurDI" else ConteneurFactory
    if name in ("AgentSupervisor", "main"):
        from .supervisor import AgentSupervisor, main

        return AgentSupervisor if name == "AgentSupervisor" else main
    if name in (
        "PipelineStatusAggregator",
        "PipelineStatusService",
        "StaticStatusProvider",
        "ComposantStatusProvider",
    ):
        from .pipeline_status import (
            ComposantStatusProvider,
            PipelineStatusAggregator,
            PipelineStatusService,
            StaticStatusProvider,
        )

        return {
            "PipelineStatusAggregator": PipelineStatusAggregator,
            "PipelineStatusService": PipelineStatusService,
            "StaticStatusProvider": StaticStatusProvider,
            "ComposantStatusProvider": ComposantStatusProvider,
        }[name]
    if name == "demarrer_serveur_status":
        from .api_status import demarrer_serveur_status

        return demarrer_serveur_status
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
