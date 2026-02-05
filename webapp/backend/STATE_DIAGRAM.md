# Diagramme d'État Final - Système IDS2

## Diagramme d'État Principal (Agent Supervisor)

```mermaid
stateDiagram-v2
    [*] --> Initializing: Démarrage
    
    state Initializing {
        [*] --> LoadingConfig
        LoadingConfig --> ValidatingConfig: Config chargé
        ValidatingConfig --> ConfigValid: Validation OK
        ValidatingConfig --> ConfigError: Validation échouée
        ConfigValid --> [*]
        ConfigError --> [*]
    }
    
    Initializing --> ConfigError: Config invalide
    Initializing --> ComponentsStarting: Config valide
    
    state ComponentsStarting {
        [*] --> StartingResourceController
        StartingResourceController --> StartingDockerManager: ResourceController OK
        StartingDockerManager --> StartingSuricataManager: DockerManager OK
        StartingSuricataManager --> AllComponentsStarted: SuricataManager OK
        AllComponentsStarted --> [*]
    }
    
    ComponentsStarting --> Running: Tous les composants démarrés
    ComponentsStarting --> Error: Échec démarrage composant
    
    state Running {
        [*] --> Monitoring
        Monitoring --> CheckingHealth: Vérification périodique
        CheckingHealth --> NormalOperation: Tous OK
        CheckingHealth --> ComponentIssue: Problème détecté
        NormalOperation --> Monitoring: Cycle normal
        ComponentIssue --> Monitoring: Problème résolu
        ComponentIssue --> ResourceLimitExceeded: Limite atteinte
    }
    
    Running --> Monitoring: Opération normale
    Monitoring --> Running: Tout OK
    Monitoring --> Degraded: Problème composant
    Monitoring --> Error: Échec critique
    
    state Degraded {
        [*] --> DetectingIssue
        DetectingIssue --> AttemptingRecovery: Auto-réparation
        AttemptingRecovery --> RecoverySuccess: Réparation réussie
        AttemptingRecovery --> RecoveryFailed: Réparation échouée
        RecoverySuccess --> [*]
        RecoveryFailed --> [*]
    }
    
    Degraded --> Recovering: Auto-réparation
    Recovering --> Running: Réparation réussie
    Recovering --> Error: Réparation échouée
    
    state Error {
        [*] --> CriticalFailure
        CriticalFailure --> LoggingError
        LoggingError --> DeterminingAction
        DeterminingAction --> [*]
    }
    
    Error --> Restarting: Redémarrage manuel/auto
    Restarting --> Initializing: Redémarrage complet
    
    state Stopping {
        [*] --> StoppingSuricata
        StoppingSuricata --> StoppingDocker: Suricata arrêté
        StoppingDocker --> StoppingResourceController: Docker arrêté
        StoppingResourceController --> AllStopped: ResourceController arrêté
        AllStopped --> [*]
    }
    
    Running --> Stopping: Commande arrêt
    Degraded --> Stopping: Commande arrêt
    Monitoring --> Stopping: Commande arrêt
    Error --> Stopping: Commande arrêt (si possible)
    
    Stopping --> Stopped: Tout arrêté
    Stopped --> [*]: Sortie
    Stopped --> Initializing: Commande redémarrage
    
    ConfigError --> [*]: Sortie
    Error --> [*]: Erreur fatale
```

## Diagramme d'État des Composants

```mermaid
stateDiagram-v2
    [*] --> Stopped: Composant créé
    
    Stopped --> Starting: demarrer() appelé
    Starting --> Running: Démarrage réussi
    Starting --> Error: Échec démarrage
    
    Running --> Monitoring: Opération normale
    Monitoring --> Healthy: Santé OK
    Monitoring --> Unhealthy: Problème détecté
    
    Healthy --> Monitoring: Cycle de vérification
    Unhealthy --> AttemptingRecovery: Tentative récupération
    AttemptingRecovery --> Healthy: Récupération réussie
    AttemptingRecovery --> Degraded: Récupération partielle
    AttemptingRecovery --> Error: Récupération échouée
    
    Degraded --> AttemptingRecovery: Nouvelle tentative
    Degraded --> Error: Problème critique
    
    Running --> Stopping: arreter() appelé
    Monitoring --> Stopping: Commande arrêt
    Healthy --> Stopping: Commande arrêt
    Unhealthy --> Stopping: Commande arrêt
    Degraded --> Stopping: Commande arrêt
    Error --> Stopping: Commande arrêt (si possible)
    
    Stopping --> Stopped: Arrêt complet
    Stopped --> [*]: Destruction
    
    note right of Running
        État principal
        du composant
    end note
    
    note right of Monitoring
        Vérification périodique
        de la santé
    end note
```

## Diagramme d'État du Pipeline

```mermaid
stateDiagram-v2
    [*] --> Unknown: Pipeline initialisé
    
    Unknown --> Collecting: Collecte des statuts
    Collecting --> Processing: Statuts collectés
    
    Processing --> OK: Tous les composants sains
    Processing --> Degraded: Certains composants en erreur
    Processing --> KO: Tous les composants en erreur
    
    OK --> Collecting: Cycle de collecte
    Degraded --> Collecting: Cycle de collecte
    KO --> Collecting: Cycle de collecte
    
    OK --> Degraded: Problème détecté
    Degraded --> OK: Problème résolu
    Degraded --> KO: Problème critique
    
    KO --> Recovering: Tentative récupération
    Recovering --> Degraded: Récupération partielle
    Recovering --> OK: Récupération complète
    Recovering --> KO: Récupération échouée
    
    note right of OK
        État: "ok"
        Tous les composants sains
    end note
    
    note right of Degraded
        État: "degrade"
        Certains composants
        en erreur
    end note
    
    note right of KO
        État: "ko"
        Tous les composants
        en erreur
    end note
```

## Diagramme d'État du Déploiement

```mermaid
stateDiagram-v2
    [*] --> NotStarted: Déploiement initialisé
    
    NotStarted --> CheckingPrerequisites: Démarrage
    CheckingPrerequisites --> PrerequisitesOK: Prérequis validés
    CheckingPrerequisites --> PrerequisitesFailed: Prérequis manquants
    
    PrerequisitesOK --> InstallingDependencies: Installation dépendances
    PrerequisitesFailed --> [*]: Échec
    
    InstallingDependencies --> DependenciesInstalled: Dépendances installées
    InstallingDependencies --> DependenciesFailed: Échec installation
    
    DependenciesInstalled --> BuildingDockerImages: Build images Docker
    DependenciesFailed --> [*]: Échec
    
    BuildingDockerImages --> ImagesBuilt: Images construites
    BuildingDockerImages --> BuildFailed: Échec build
    
    ImagesBuilt --> StartingServices: Démarrage services
    BuildFailed --> [*]: Échec
    
    StartingServices --> ServicesStarted: Services démarrés
    StartingServices --> ServicesFailed: Échec démarrage
    
    ServicesStarted --> VerifyingHealth: Vérification santé
    ServicesFailed --> [*]: Échec
    
    VerifyingHealth --> HealthOK: Santé OK
    VerifyingHealth --> HealthFailed: Santé échouée
    
    HealthOK --> Deployed: Déploiement réussi
    HealthFailed --> Retrying: Nouvelle tentative
    
    Retrying --> StartingServices: Retry
    Retrying --> [*]: Max tentatives atteint
    
    Deployed --> [*]: Succès
```

## Diagramme d'État des Services Docker

```mermaid
stateDiagram-v2
    [*] --> NotCreated: Service non créé
    
    NotCreated --> Creating: Création conteneur
    Creating --> Created: Conteneur créé
    Creating --> CreationFailed: Échec création
    
    Created --> Starting: Démarrage
    Starting --> Running: Service démarré
    Starting --> StartFailed: Échec démarrage
    
    Running --> Healthy: Health check OK
    Running --> Unhealthy: Health check échoué
    Running --> Stopping: Commande arrêt
    
    Healthy --> Running: Cycle normal
    Unhealthy --> Restarting: Redémarrage automatique
    Unhealthy --> Stopping: Arrêt manuel
    
    Restarting --> Starting: Nouveau démarrage
    Restarting --> RestartFailed: Échec redémarrage
    
    Stopping --> Stopped: Service arrêté
    Stopped --> Removing: Suppression
    Removing --> [*]: Supprimé
    
    CreationFailed --> [*]: Échec fatal
    StartFailed --> [*]: Échec fatal
    RestartFailed --> [*]: Échec fatal
```

## Légende des États

### États Principaux
- **Initializing**: Initialisation du système
- **ComponentsStarting**: Démarrage des composants
- **Running**: Système en fonctionnement
- **Monitoring**: Surveillance active
- **Degraded**: Système dégradé mais fonctionnel
- **Recovering**: Récupération en cours
- **Error**: Erreur critique
- **Stopping**: Arrêt en cours
- **Stopped**: Arrêté

### États des Composants
- **Stopped**: Composant arrêté
- **Starting**: Démarrage en cours
- **Running**: En fonctionnement
- **Monitoring**: Surveillance active
- **Healthy**: Santé OK
- **Unhealthy**: Problème détecté
- **AttemptingRecovery**: Tentative de récupération
- **Degraded**: État dégradé
- **Error**: Erreur

### États du Pipeline
- **Unknown**: État inconnu
- **Collecting**: Collecte des statuts
- **Processing**: Traitement des statuts
- **OK**: Tous les composants sains
- **Degraded**: Certains composants en erreur
- **KO**: Tous les composants en erreur
- **Recovering**: Récupération en cours

## Transitions Principales

1. **Démarrage**: `[*] → Initializing → ComponentsStarting → Running`
2. **Opération normale**: `Running → Monitoring → Running`
3. **Détection problème**: `Monitoring → Degraded → Recovering → Running`
4. **Erreur critique**: `Any → Error → Restarting → Initializing`
5. **Arrêt**: `Any → Stopping → Stopped → [*]`

## Notes d'Implémentation

- Les transitions sont gérées par `AgentSupervisor`
- Les composants héritent de `BaseComponent` qui gère les états de base
- Le `PipelineStatusAggregator` collecte et agrège les statuts
- Les états sont persistés dans `shared_state` pour la communication inter-processus
- Les erreurs déclenchent des mécanismes de récupération automatique
- Les arrêts gracieux sont gérés via `SIGTERM`/`SIGINT`
