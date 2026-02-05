"""
Pipeline status aggregation and minimal service.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from enum import Enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..domain import ConditionSante, MetriquesSystem
from .decorateurs import log_appel, metriques, retry

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ..interfaces import GestionnaireComposant, MetriquesProvider, PipelineStatusProvider


class PipelineState(Enum):
    PIPE_UNKNOWN = "PipeUnknown"
    PIPE_COLLECTING = "PipeCollecting"
    PIPE_PROCESSING = "PipeProcessing"
    PIPE_OK = "PipeOK"
    PIPE_DEGRADED = "PipeDegraded"
    PIPE_KO = "PipeKO"
    PIPE_RECOVERING = "PipeRecovering"


class StaticStatusProvider:
    """Provide a fixed status payload."""

    def __init__(
        self,
        nom: str,
        sain: bool = True,
        message: str = "statut non verifie",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.nom = nom
        self._sain = sain
        self._message = message
        self._details = details or {}

    @log_appel()
    @metriques("pipeline_status.static")
    async def fournir_statut(self) -> ConditionSante:
        return ConditionSante(
            nom_composant=self.nom,
            sain=self._sain,
            message=self._message,
            details=self._details,
        )


class ComposantStatusProvider:
    """Adapter for GestionnaireComposant."""

    def __init__(self, nom: str, composant: GestionnaireComposant) -> None:
        self.nom = nom
        self._composant = composant

    @log_appel()
    @metriques("pipeline_status.component")
    @retry(nb_tentatives=2, delai_initial=0.5)
    async def fournir_statut(self) -> ConditionSante:
        statut = await self._composant.verifier_sante()
        if statut.nom_composant != self.nom:
            return ConditionSante(
                nom_composant=self.nom,
                sain=statut.sain,
                message=statut.message,
                details=statut.details,
            )
        return statut


class PipelineStatusAggregator:
    """Aggregate status from all providers."""

    def __init__(self, providers: Iterable[PipelineStatusProvider] | None = None) -> None:
        self._providers: list[PipelineStatusProvider] = list(providers) if providers else []
        self._metriques_provider: MetriquesProvider | None = None
        self._state = PipelineState.PIPE_UNKNOWN

    def ajouter_provider(self, provider: PipelineStatusProvider) -> None:
        self._providers.append(provider)

    def retirer_provider(self, provider: PipelineStatusProvider) -> None:
        if provider in self._providers:
            self._providers.remove(provider)

    def definir_metriques_provider(self, provider: MetriquesProvider) -> None:
        self._metriques_provider = provider

    @log_appel()
    @metriques("pipeline_status.collecte")
    @retry(nb_tentatives=2, delai_initial=0.5)
    async def collecter(self) -> dict[str, Any]:
        self._state = PipelineState.PIPE_COLLECTING
        timestamp = _utc_iso()
        if not self._providers:
            self._state = PipelineState.PIPE_UNKNOWN
            return {
                "timestamp": timestamp,
                "etat_pipeline": "inconnu",
                "composants": [],
                "resume": {"total": 0, "sains": 0, "erreurs": 0},
                "erreurs": ["aucun provider enregistre"],
            }

        results = await asyncio.gather(
            *(provider.fournir_statut() for provider in self._providers),
            return_exceptions=True,
        )

        self._state = PipelineState.PIPE_PROCESSING
        composants: list[dict[str, Any]] = []
        erreurs: list[str] = []
        sains = 0

        for provider, resultat in zip(self._providers, results, strict=False):
            if isinstance(resultat, Exception):
                erreurs.append(f"{_provider_nom(provider)}: {resultat}")
                composants.append(_erreur_component(provider, str(resultat)))
                continue

            if not isinstance(resultat, ConditionSante):
                message = "statut invalide fourni"
                erreurs.append(f"{_provider_nom(provider)}: {message}")
                composants.append(_erreur_component(provider, message))
                continue

            if resultat.sain:
                sains += 1
            composants.append(_condition_to_dict(resultat))

        total = len(composants)
        etat = _etat_pipeline(total, sains)
        self._update_fsm_state(etat)

        payload: dict[str, Any] = {
            "timestamp": timestamp,
            "etat_pipeline": etat,
            "composants": composants,
            "resume": {"total": total, "sains": sains, "erreurs": len(erreurs)},
            "erreurs": erreurs,
        }
        metriques = await _collecter_metriques(self._metriques_provider)
        if metriques is not None:
            payload["metriques"] = metriques
        return payload

    def _update_fsm_state(self, etat: str) -> None:
        target = {
            "inconnu": PipelineState.PIPE_UNKNOWN,
            "ok": PipelineState.PIPE_OK,
            "degrade": PipelineState.PIPE_DEGRADED,
            "ko": PipelineState.PIPE_KO,
        }.get(etat, PipelineState.PIPE_UNKNOWN)

        if self._state == PipelineState.PIPE_RECOVERING:
            self._state = target
            return

        if self._state == PipelineState.PIPE_KO and target in (
            PipelineState.PIPE_OK,
            PipelineState.PIPE_DEGRADED,
        ):
            self._state = PipelineState.PIPE_RECOVERING
            return

        self._state = target

    def etat_fsm(self) -> PipelineState:
        return self._state


class PipelineStatusService:
    """Minimal HTTP-ready service."""

    def __init__(self, aggregator: PipelineStatusAggregator) -> None:
        self._aggregator = aggregator

    @log_appel()
    @metriques("pipeline_status.endpoint")
    async def obtenir_statut(self) -> dict[str, Any]:
        return await self._aggregator.collecter()


def _etat_pipeline(total: int, sains: int) -> str:
    if total == 0:
        return "inconnu"
    if sains == total:
        return "ok"
    if sains == 0:
        return "ko"
    return "degrade"


def _utc_iso() -> str:
    return f"{datetime.utcnow().isoformat()}Z"


def _provider_nom(provider: PipelineStatusProvider) -> str:
    nom = getattr(provider, "nom", None)
    if isinstance(nom, str) and nom.strip():
        return nom
    return provider.__class__.__name__


def _condition_to_dict(condition: ConditionSante) -> dict[str, Any]:
    data = asdict(condition)
    data["derniere_verification"] = f"{condition.derniere_verification.isoformat()}Z"
    return data


def _erreur_component(
    provider: PipelineStatusProvider,
    message: str,
) -> dict[str, Any]:
    return {
        "nom_composant": _provider_nom(provider),
        "sain": False,
        "message": message,
        "derniere_verification": _utc_iso(),
        "details": {},
    }


def _normaliser_metriques(brut: Any) -> dict[str, Any] | None:
    if brut is None:
        return None
    if isinstance(brut, MetriquesSystem):
        return {
            "cpu_usage": brut.cpu_usage,
            "ram_usage": brut.ram_usage,
            "alertes_par_seconde": brut.alertes_par_seconde,
            "alertes_en_queue": brut.alertes_en_queue,
            "uptime_secondes": brut.uptime_secondes,
            "erreurs_recentes": brut.erreurs_recentes,
            "metadata": brut.metadata,
        }
    if isinstance(brut, dict):
        return brut
    return {"raw": brut}


async def _collecter_metriques(
    provider: MetriquesProvider | None,
) -> dict[str, Any] | None:
    if provider is None:
        return None
    try:
        brut = await provider.collecter_metriques()
    except Exception:
        return None
    return _normaliser_metriques(brut)


__all__ = [
    "ComposantStatusProvider",
    "PipelineStatusAggregator",
    "PipelineStatusService",
    "PipelineState",
    "StaticStatusProvider",
]
