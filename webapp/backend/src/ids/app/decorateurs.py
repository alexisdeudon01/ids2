"""
Décorateurs - Extend comportements des fonctions avec logging, métriques, etc.

Implémente les décorateurs mentionnés dans les exigences (@log_appel, @metriques).
"""

# Pour les décorateurs async
import asyncio
import functools
import inspect
import logging
import time
from collections.abc import Callable
from typing import TypeVar, cast

T = TypeVar("T")


def log_appel(
    niveau: int = logging.INFO,
    afficher_args: bool = True,
    afficher_retour: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Décorateur pour logger les appels de fonction.

    Utilisation :
        @log_appel()
        def ma_fonction(x: int) -> int:
            return x * 2

        @log_appel(niveau=logging.DEBUG, afficher_args=False)
        async def ma_fonction_async():
            ...

    Args:
        niveau: Niveau de log (logging.INFO, DEBUG, etc.)
        afficher_args: Afficher les arguments
        afficher_retour: Afficher la valeur de retour
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        logger = logging.getLogger(func.__module__)

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                msg = f"Appel: {func.__name__}"
                if afficher_args:
                    msg += f"({args}, {kwargs})"
                logger.log(niveau, msg)

                try:
                    resultat = await func(*args, **kwargs)
                    if afficher_retour:
                        logger.log(niveau, f"Retour: {func.__name__} -> {resultat}")
                    return resultat
                except Exception as e:
                    logger.error(f"Exception dans {func.__name__}: {e}")
                    raise

            return cast("Callable[..., T]", async_wrapper)
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                msg = f"Appel: {func.__name__}"
                if afficher_args:
                    msg += f"({args}, {kwargs})"
                logger.log(niveau, msg)

                try:
                    resultat = func(*args, **kwargs)
                    if afficher_retour:
                        logger.log(niveau, f"Retour: {func.__name__} -> {resultat}")
                    return resultat
                except Exception as e:
                    logger.error(f"Exception dans {func.__name__}: {e}")
                    raise

            return cast("Callable[..., T]", sync_wrapper)

    return decorator


def metriques(nom_metrique: str | None = None) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Décorateur pour collecter des métriques (durée d'exécution).

    Utilisation :
        @metriques("temps_traitement_alerte")
        def traiter_alerte(alerte: AlerteIDS) -> None:
            ...

    Args:
        nom_metrique: Nom de la métrique (par défaut: nom de la fonction)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        logger = logging.getLogger(func.__module__)
        metrique_name = nom_metrique or f"execution_time.{func.__name__}"

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                debut = time.time()
                try:
                    resultat = await func(*args, **kwargs)
                    return resultat
                finally:
                    duree = time.time() - debut
                    logger.debug(f"{metrique_name}: {duree:.3f}s")

            return cast("Callable[..., T]", async_wrapper)
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                debut = time.time()
                try:
                    resultat = func(*args, **kwargs)
                    return resultat
                finally:
                    duree = time.time() - debut
                    logger.debug(f"{metrique_name}: {duree:.3f}s")

            return cast("Callable[..., T]", sync_wrapper)

    return decorator


def cache_resultat(
    ttl_secondes: int = 300,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Décorateur pour mettre en cache le résultat d'une fonction.

    Utilisation :
        @cache_resultat(ttl_secondes=60)
        def configuration_statique() -> Dict:
            return loads_expensive_config()

    Args:
        ttl_secondes: Durée de vie du cache en secondes
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache = {}
        cache_time = {}

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            clé = (args, tuple(sorted(kwargs.items())))
            maintenant = time.time()

            if clé in cache and (maintenant - cache_time[clé]) < ttl_secondes:
                return cache[clé]

            resultat = func(*args, **kwargs)
            cache[clé] = resultat
            cache_time[clé] = maintenant
            return resultat

        return cast("Callable[..., T]", wrapper)

    return decorator


def retry(
    nb_tentatives: int = 3,
    delai_initial: float = 1.0,
    backoff: float = 2.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Décorateur pour réessayer une fonction en cas d'erreur.

    Utilisation :
        @retry(nb_tentatives=3, delai_initial=0.5, backoff=2.0)
        async def appel_api_instable():
            ...

    Args:
        nb_tentatives: Nombre total de tentatives
        delai_initial: Délai initial en secondes
        backoff: Multiplicateur de délai à chaque tentative
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        logger = logging.getLogger(func.__module__)

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                delai = delai_initial
                dernier_erreur = None

                for tentative in range(nb_tentatives):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        dernier_erreur = e
                        if tentative < nb_tentatives - 1:
                            logger.warning(
                                f"Tentative {tentative + 1}/{nb_tentatives} "
                                f"échouée pour {func.__name__}, "
                                f"nouvelle tentative dans {delai}s"
                            )
                            await asyncio.sleep(delai)
                            delai *= backoff

                logger.error(f"{func.__name__} échoué après {nb_tentatives} tentatives")
                raise dernier_erreur

            return cast("Callable[..., T]", async_wrapper)
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                delai = delai_initial
                dernier_erreur = None

                for tentative in range(nb_tentatives):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        dernier_erreur = e
                        if tentative < nb_tentatives - 1:
                            logger.warning(
                                f"Tentative {tentative + 1}/{nb_tentatives} "
                                f"échouée pour {func.__name__}, "
                                f"nouvelle tentative dans {delai}s"
                            )
                            time.sleep(delai)
                            delai *= backoff

                logger.error(f"{func.__name__} échoué après {nb_tentatives} tentatives")
                raise dernier_erreur

            return cast("Callable[..., T]", sync_wrapper)

    return decorator


__all__ = [
    "cache_resultat",
    "log_appel",
    "metriques",
    "retry",
]
