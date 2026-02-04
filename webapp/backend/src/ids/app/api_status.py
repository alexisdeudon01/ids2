"""
Endpoint HTTP pour le statut du pipeline (FastAPI).
"""

from typing import Any

import uvicorn
from fastapi import FastAPI

from .decorateurs import log_appel, metriques
from .pipeline_status import (
    PipelineStatusAggregator,
    PipelineStatusService,
    StaticStatusProvider,
)

app = FastAPI(title="IDS2 Pipeline Status")

_aggregator = PipelineStatusAggregator(
    providers=[StaticStatusProvider("agent")],
)
_service = PipelineStatusService(_aggregator)


@app.get("/status")
@log_appel()
@metriques("api.status")
async def status() -> dict[str, Any]:
    return await _service.obtenir_statut()


@app.get("/health")
@log_appel()
@metriques("api.health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def demarrer_serveur_status(host: str = "0.0.0.0", port: int = 8080) -> None:
    # bandit: B104 - Binding to 0.0.0.0 is intentional for API server
    # This allows the service to be accessible from the network
    uvicorn.run("ids.app.api_status:app", host=host, port=port, reload=False)


__all__ = ["app", "demarrer_serveur_status"]
