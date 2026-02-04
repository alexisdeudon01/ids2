# 📐 Plan de Refactorisation Architecturale - Projet IDS

## Vue d'ensemble exécutive

Ce document détaille la refactorisation complète du système IDS pour adopter une architecture hybride POO/Data-Oriented avec les principes SOLID, l'injection de dépendances, et une intégration CI/CD robuste.

---

## 1. État Actuel vs État Cible

### ❌ Problèmes Identifiés dans la Structure Actuelle

```
legacy_app/
├── main.py              # 351 lignes - trop responsable
├── modules/             # 13 fichiers plats - pas de groupement logique
│   ├── base_component.py
│   ├── config_manager.py
│   ├── suricata_manager.py
│   ├── vector_manager.py
│   ├── docker_manager.py
│   └── ... (8 autres)
└── tests/               # Tests fragmentés, pas de conftest, pas de markers
    └── test_*.py        # 12 fichiers de test sans organisation
```

**Problèmes clés :**

1. ❌ **Couplage fort** : `ResourceController` appelle directement `SuricataManager` (pas d'abstraction)
2. ❌ **Pas d'injection de dépendances** : Initialisation manuelle des dépendances dans `main.py`
3. ❌ **Mélange POO/Données** : Pas de modèles de données structurés (dataclasses)
4. ❌ **Tests non organisés** : Pas de fixtures réutilisables, pas de markers
5. ❌ **Configuration manuelle** : État partagé de bas niveau au lieu de conteneur DI
6. ❌ **Documentation** : Absence de docstrings et d'architecture documentée

---

### ✅ Architecture Cible

```
ids/                                    # Nouveau répertoire racine du projet
├── src/
│   └── ids/                            # Package principal
│       ├── __init__.py
│       ├── domain/                     # 📊 Entités de domaine (Data-Oriented)
│       │   ├── __init__.py
│       │   ├── alerte.py              # @dataclass AlerteIDS, AlerteSecurite
│       │   ├── configuration.py        # @dataclass ConfigurationIDS
│       │   ├── metriques.py           # @dataclass MetriquesSystem
│       │   └── exceptions.py          # Exceptions métier
│       │
│       ├── interfaces/                 # 🔌 Abstractions (Protocol)
│       │   ├── __init__.py
│       │   ├── alerte_source.py       # Protocol AlerteSource
│       │   ├── gestionnaire.py        # Protocol GestionnaireComposant
│       │   ├── persistance.py         # Protocol PersistanceAlertes
│       │   └── config.py              # Protocol GestionnaireConfig
│       │
│       ├── suricata/                   # 🦑 Package Suricata (logique métier)
│       │   ├── __init__.py
│       │   ├── manager.py             # SuricataManager (impl. AlerteSource)
│       │   ├── config.py              # Générateur config Suricata
│       │   └── parser.py              # Parseur EVE.json
│       │
│       ├── composants/                 # 🧩 Composants (POO, BaseComponent)
│       │   ├── __init__.py
│       │   ├── base.py                # BaseComponent amélioré
│       │   ├── resource_controller.py # Gestion ressources
│       │   ├── docker_manager.py      # Gestion Docker
│       │   ├── vector_manager.py      # Gestion Vector
│       │   ├── connectivity.py        # Tests connectivité
│       │   └── metrics_server.py      # Serveur Prometheus
│       │
│       ├── infrastructure/             # 🏗️ Services (AWS, Redis, etc.)
│       │   ├── __init__.py
│       │   ├── aws_manager.py         # Client AWS/OpenSearch
│       │   ├── redis_client.py        # Client Redis
│       │   └── logger.py              # Logging centralisé
│       │
│       ├── app/                        # 🚀 Orchestration
│       │   ├── __init__.py
│       │   ├── supervisor.py          # AgentSupervisor refactorisé
│       │   ├── container.py           # Conteneur DI (punq)
│       │   └── decorateurs.py         # @log_appel, @metriques, etc.
│       │
│       └── config/                     # ⚙️ Configuration
│           ├── __init__.py
│           ├── loader.py              # ConfigManager refactorisé
│           ├── schemas.py             # Validation config (Pydantic)
│           └── defaults.yaml
│
├── tests/
│   ├── conftest.py                     # Fixtures pytest globales
│   ├── pytest.ini                      # Configuration pytest
│   ├── markers.ini                     # Définition des markers
│   │
│   ├── unit/                           # Tests unitaires
│   │   ├── test_domain/
│   │   │   ├── test_alerte.py
│   │   │   └── test_configuration.py
│   │   ├── test_suricata/
│   │   │   ├── test_manager.py
│   │   │   ├── test_parser.py
│   │   │   └── test_config.py
│   │   └── test_composants/
│   │       ├── test_resource_controller.py
│   │       └── ...
│   │
│   ├── integration/                    # Tests intégration
│   │   ├── test_pipeline.py           # @pytest.mark.performance
│   │   ├── test_docker_suricata.py    # @pytest.mark.suricata
│   │   └── test_aws_connectivity.py   # @pytest.mark.aws
│   │
│   ├── fixtures/
│   │   ├── __init__.py
│   │   ├── alerte_fixtures.py        # Fixtures pour alertes
│   │   ├── config_fixtures.py        # Fixtures pour config
│   │   └── container_fixtures.py     # Fixtures pour DI
│   │
│   └── mocks/
│       ├── __init__.py
│       ├── mock_suricata.py
│       └── mock_aws.py
│
├── pyproject.toml                      # Nouvelle gestion de dépendances
├── requirements.txt                    # + punq, pydantic, pytest-markers
├── pytest.ini                          # Configuration pytest
├── setup.py
│
└── docs/
    ├── ARCHITECTURE.md                 # Documentation architecture
    ├── DI_GUIDE.md                     # Guide injection dépendances
    └── DEPLOYMENT.md                   # Guide déploiement Tailscale
```

---

## 2. Phases de Refactorisation

### Phase 1️⃣ : Modèle de Données (1-2 jours)

**Objectif** : Définir les entités de domaine avec dataclasses

**Fichiers à créer** :
- `src/ids/domain/alerte.py`
- `src/ids/domain/configuration.py`
- `src/ids/domain/metriques.py`
- `src/ids/domain/exceptions.py`

**Exemple** :
```python
# src/ids/domain/alerte.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any
from enum import Enum

class SeveriteAlerte(Enum):
    CRITIQUE = "critique"
    HAUTE = "haute"
    MOYENNE = "moyenne"
    BASSE = "basse"

class TypeAlerte(Enum):
    INTRUSION = "intrusion"
    ANOMALIE = "anomalie"
    CONFORMITE = "conformite"

@dataclass(frozen=True)
class AlerteIDS:
    """Entité immuable représentant une alerte de sécurité IDS."""
    timestamp: datetime
    severite: SeveriteAlerte
    type_alerte: TypeAlerte
    source_ip: str
    destination_ip: str
    port: int
    protocole: str
    signature: str
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        return hash((self.timestamp, self.source_ip, self.destination_ip, self.port))
```

---

### Phase 2️⃣ : Interfaces Protocol (1 jour)

**Objectif** : Définir les contrats de dépendances sans implémentation

**Fichiers à créer** :
- `src/ids/interfaces/alerte_source.py`
- `src/ids/interfaces/gestionnaire.py`
- `src/ids/interfaces/config.py`

**Exemple** :
```python
# src/ids/interfaces/alerte_source.py
from typing import Protocol, List, AsyncGenerator
from ..domain.alerte import AlerteIDS

class AlerteSource(Protocol):
    """Interface pour les sources d'alertes."""
    
    async def fournir_alertes(self) -> AsyncGenerator[AlerteIDS, None]:
        """Fournit un flux continu d'alertes."""
        ...
    
    async def valider_connexion(self) -> bool:
        """Valide la connexion à la source."""
        ...

class GestionnaireComposant(Protocol):
    """Interface pour les gestionnaires de composants."""
    
    async def demarrer(self) -> None:
        """Démarre le composant."""
        ...
    
    async def arreter(self) -> None:
        """Arrête le composant."""
        ...
    
    async def verifier_sante(self) -> bool:
        """Vérifie l'état de santé du composant."""
        ...
```

---

### Phase 3️⃣ : Injection de Dépendances (1-2 jours)

**Objectif** : Mettre en place le conteneur DI avec punq

**Fichiers à créer** :
- `src/ids/app/container.py` (Conteneur DI)
- `src/ids/app/decorateurs.py` (Décorateurs @log_appel, @metriques)

**Exemple** :
```python
# src/ids/app/container.py
import punq
from typing import Dict, Any
from ..interfaces.alerte_source import AlerteSource
from ..interfaces.config import GestionnaireConfig
from ..suricata.manager import SuricataManager
from ..composants.resource_controller import ResourceController

class ConteneurDI:
    """Conteneur d'injection de dépendances."""
    
    def __init__(self):
        self.container = punq.Container()
    
    def enregistrer_services(self, config: Dict[str, Any]) -> None:
        """Enregistre tous les services du conteneur."""
        
        # Enregistrer les services singleton
        self.container.register(
            GestionnaireConfig,
            instance=ConfigManager(config)
        )
        
        # Enregistrer AlerteSource (impl. par SuricataManager)
        self.container.register(
            AlerteSource,
            factory=lambda: SuricataManager(...)
        )
        
        # Enregistrer les composants
        self.container.register(ResourceController)
        self.container.register(DockerManager)
        
    def resoudre(self, service_type):
        """Résout et instancie un service."""
        return self.container.resolve(service_type)
```

---

### Phase 4️⃣ : Refactoriser Composants (2-3 jours)

**Objectif** : Adapter les composants existants aux interfaces

**Approche** :
1. Garder `BaseComponent` mais l'améliorer avec protocoles
2. Implémenter `AlerteSource` dans `SuricataManager`
3. Injecter `AlerteSource` dans `ResourceController` (au lieu de dépendre directement de `SuricataManager`)

**Exemple** :
```python
# src/ids/suricata/manager.py
from typing import AsyncGenerator
from ..interfaces.alerte_source import AlerteSource
from ..domain.alerte import AlerteIDS
from ..composants.base import BaseComponent

class SuricataManager(BaseComponent, AlerteSource):
    """Gère Suricata et fournit un flux d'alertes."""
    
    async def fournir_alertes(self) -> AsyncGenerator[AlerteIDS, None]:
        """Implémente AlerteSource.fournir_alertes()"""
        # Lire eve.json, parser et yielder les alertes
        while not self.is_shutdown_requested():
            alertes = self._lire_alertes_eve()
            for alerte in alertes:
                yield alerte
    
    async def valider_connexion(self) -> bool:
        """Implémente AlerteSource.valider_connexion()"""
        return self.suricata_process and self.suricata_process.poll() is None
```

---

### Phase 5️⃣ : Tests & Fixtures (2 jours)

**Fichiers à créer** :
- `tests/conftest.py` - Fixtures globales
- `tests/pytest.ini` - Configuration markers
- `tests/fixtures/` - Fixtures réutilisables

**Exemple pytest.ini** :
```ini
[pytest]
markers =
    suricata: Tests impliquant Suricata
    performance: Tests de performance
    aws: Tests de connectivité AWS
    integration: Tests d'intégration système
    unit: Tests unitaires
    slow: Tests lents
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --strict-markers --cov=src/ids
```

---

### Phase 6️⃣ : Pipeline CI/CD (1-2 jours)

**Fichier** : `deploy/push_to_pi.sh` (script de déploiement)

**Fonctionnalités** :
- Vérification de connectivité (SSH, AWS, Docker)
- Build et push de l'image Docker vers le Pi
- Synchronisation des fichiers nécessaires
- Activation des services systemd et Docker Compose

---

## 3. Dépendances à Ajouter

```diff
requirements.txt

+ punq==1.0.0                # Injection de dépendances
+ pydantic==2.0+             # Validation de configuration
+ pytest-cov==4.0+           # Couverture de tests
+ pytest-asyncio==0.21+      # Support async tests
+ pytest-markers==0.5+       # Gestion avancée des markers
+ dataclasses-json==0.5+     # Serialization dataclasses
+ tailscale>=1.0             # Client Tailscale (optionnel)
```

---

## 4. Plan d'Action Détaillé

| Phase | Tâche | Durée | Dépendances |
|-------|-------|-------|-------------|
| 1 | Créer structure domain/ | 4h | Aucune |
| 1 | Créer dataclasses | 4h | Structure |
| 2 | Créer interfaces/ | 4h | Phase 1 |
| 3 | Mettre en place punq | 8h | Phase 2 |
| 3 | Créer ConteneurDI | 4h | punq |
| 4 | Adapter SuricataManager | 8h | Phase 3 |
| 4 | Adapter ResourceController | 8h | Phase 3 |
| 4 | Adapter autres composants | 16h | Phase 3 |
| 5 | Créer conftest.py | 8h | Phase 4 |
| 5 | Écrire tests unitaires | 16h | conftest.py |
| 6 | Pipeline CI/CD | 8h | Phase 5 |
| 6 | Documentation | 8h | Phases 1-6 |
| | **TOTAL** | **~4 semaines** | |

---

## 5. Principes SOLID Appliqués

### Single Responsibility Principle (SRP)
- `AlerteIDS` : uniquement une alerte
- `SuricataManager` : uniquement Suricata
- `ResourceController` : uniquement gestion ressources

### Open/Closed Principle (OCP)
- Interfaces `Protocol` permettent extensibilité sans modification

### Liskov Substitution Principle (LSP)
- Tous les `GestionnaireComposant` peuvent être substitués

### Interface Segregation Principle (ISP)
- `AlerteSource` séparé de `GestionnaireComposant`

### Dependency Inversion Principle (DIP)
- `ResourceController` dépend d'`AlerteSource` (abstraction)
- Pas de `from ..suricata import SuricataManager`

---

## 6. Bénéfices Attendus

✅ **Testabilité** : Mock facile grâce aux Protocol  
✅ **Maintenabilité** : Séparation des responsabilités  
✅ **Extensibilité** : Ajouter nouvelles sources sans toucher au code existant  
✅ **Réutilisabilité** : Dataclasses et fixtures réutilisables  
✅ **Documentation** : Architecture claire et autodocumentée  
✅ **Confiance** : Tests exhaustifs avec markers  
✅ **Déploiement** : CI/CD automatis√© avec Tailscale  

---

## 7. Points Critiques à Attention

⚠️ **Migration des imports** : `from modules.` → `from ids.`  
⚠️ **État partagé** : Remplacer `multiprocessing.dict` par DI  
⚠️ **Configuration** : Validation avec Pydantic  
⚠️ **Tests async** : Utiliser `pytest-asyncio` pour `async def`  
⚠️ **Rétrocompatibilité** : Garder `config.yaml` en place  

---

## Prochaines Étapes

1. **Valider le plan** avec l'équipe
2. **Créer la structure de dossiers**
3. **Implémenter Phase 1** (domain/)
4. **Implémenter Phase 2** (interfaces/)
5. **Implémenter Phase 3** (DI)
6. **Refactoriser composants** progressivement
7. **Écrire tests** au fur et à mesure

---

**Auteur** : Architecte Senior SIXT R&D  
**Date** : 2 février 2026  
**Status** : 🟢 Prêt pour implémentation
