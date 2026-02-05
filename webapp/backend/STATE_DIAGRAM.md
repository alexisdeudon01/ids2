# FSM IDS2 (alignée avec `docs/kl.md`)

Ce document est aligné avec `docs/kl.md` et `fsm.md` (source de vérité).

```mermaid
stateDiagram-v2
    %%========== STYLES ==========
    classDef user fill:#e3f0fc,stroke:#2986cc,stroke-width:2px;
    classDef normal fill:#e2f7e1,stroke:#48b96a,stroke-width:2px;
    classDef degraded fill:#ffe279,stroke:#cba600,stroke-width:2px;
    classDef pipeline fill:#ffeac2,stroke:#f89c17,stroke-width:2px;
    classDef docker fill:#e4e4e4,stroke:#888,stroke-width:1.5px;
    classDef fatal fill:#ffe1e1,stroke:#f44336,stroke-width:2px,font-weight:bold;
    classDef stopping fill:#eee,stroke:#888,stroke-width:2px;
    
    %%========== USER & META ==========
    [*] --> WaitUser : "System startup"
    WaitUser: Awaiting user action
    WaitUser --> StartCommand: "User: Start system"
    WaitUser --> Stopped: "User cancels"
    class WaitUser,StartCommand user

    %%========== MAIN SUPERVISOR ==========
    StartCommand --> Initializing
    state Initializing {
        [*] --> LoadingConfig
        LoadingConfig --> ValidatingConfig : "Config loaded"
        ValidatingConfig --> ConfigValid : "Validation OK"
        ValidatingConfig --> ConfigError : "Validation failed"
        ConfigValid --> [*]
        ConfigError --> [*]
    }
    Initializing --> ComponentsStarting: "Init success"
    Initializing --> Stopped: "Config failed"
    class Initializing normal

    %%==== COMPONENTS STARTUP (SUPERVISED) ====
    state ComponentsStarting {
        [*] --> StartResourceController
        StartResourceController --> StartDockerManager: "Resource Ctrl OK"
        StartDockerManager --> StartSuricataManager: "DockerMgr OK"
        StartSuricataManager --> AllComponentsStarted: "SuricataMgr OK"
        AllComponentsStarted --> [*]
    }
    ComponentsStarting --> SupervisorRunning: "All started"
    ComponentsStarting --> Stopped: "Startup failed"
    class ComponentsStarting normal

    %%==== RUNNING SUPER SUPERVISOR ====
    state SupervisorRunning {
        [*] --> SupervisorMonitoring: "Begin monitor"
        SupervisorMonitoring --> HealthOK: "All healthy"
        SupervisorMonitoring --> SupervisorDegraded: "Problem detected"
        HealthOK --> SupervisorMonitoring: "Cycle"
        SupervisorDegraded --> SupervisorRecovering: "Self-repair"
        SupervisorRecovering --> SupervisorMonitoring: "Recovered"
        SupervisorRecovering --> Stopped: "Unrecoverable"
    }
    SupervisorRunning --> Components: "Operate components"
    SupervisorRunning --> Pipeline: "Run pipeline"
    SupervisorRunning --> Deployment: "Deployment process"
    SupervisorRunning --> DockerServices: "Supervise Docker"
    SupervisorRunning --> Stopping: "Stop requested"
    class SupervisorRunning,SupervisorMonitoring,HealthOK normal
    class SupervisorDegraded,SupervisorRecovering degraded

    %%========== COMPONENT STATE MACHINE ==========
    state Components as "Component States" {
        [*] --> CompStopped : "Created"
        CompStopped --> CompStarting : "start() called"
        CompStarting --> CompRunning : "Startup OK"
        CompStarting --> CompError : "Startup failed"
        CompRunning --> CompMonitoring : "Normal op"
        CompMonitoring --> CompHealthy : "Health OK"
        CompMonitoring --> CompUnhealthy : "Problem detected"
        CompHealthy --> CompMonitoring : "Check cycle"
        CompUnhealthy --> CompRecovering : "Try recover"
        CompRecovering --> CompHealthy : "Recovered"
        CompRecovering --> CompDegraded : "Partial recover"
        CompRecovering --> CompError : "Recovery failed"
        CompDegraded --> CompRecovering : "New try"
        CompDegraded --> CompError : "Critical error"
        CompRunning --> CompStopping : "stop() called"
        CompMonitoring --> CompStopping : "stop command"
        CompHealthy --> CompStopping : "stop command"
        CompUnhealthy --> CompStopping : "stop command"
        CompDegraded --> CompStopping : "stop command"
        CompError --> CompStopping : "stop if possible"
        CompStopping --> CompStopped : "Fully stopped"
        CompStopped --> [*]: "Destroyed"
    }
    class Components,CompStopped,CompStarting,CompRunning,CompMonitoring,CompHealthy normal
    class CompUnhealthy,CompRecovering,CompDegraded degraded
    class CompError fatal
    class CompStopping stopping

    %%========== PIPELINE STATE MACHINE ==========
    state Pipeline as "Status Pipeline" {
        [*] --> PipeUnknown : "Pipeline init"
        PipeUnknown --> PipeCollecting : "Collect statuses"
        PipeCollecting --> PipeProcessing : "Collected"
        PipeProcessing --> PipeOK : "All healthy"
        PipeProcessing --> PipeDegraded : "Some errors"
        PipeProcessing --> PipeKO : "All error"
        PipeOK --> PipeCollecting : "Collect cycle"
        PipeDegraded --> PipeCollecting : "Collect cycle"
        PipeKO --> PipeCollecting : "Collect cycle"
        PipeOK --> PipeDegraded : "Problem develops"
        PipeDegraded --> PipeOK : "Back to healthy"
        PipeDegraded --> PipeKO : "Problem worsens"
        PipeKO --> PipeRecovering : "Try recover"
        PipeRecovering --> PipeDegraded : "Partial recover"
        PipeRecovering --> PipeOK : "Full recover"
        PipeRecovering --> PipeKO : "Recovery failed"
    }
    class Pipeline,PipeUnknown,PipeCollecting,PipeProcessing pipeline
    class PipeOK normal
    class PipeDegraded,PipeRecovering degraded
    class PipeKO fatal

    %%========== DEPLOYMENT STATE MACHINE ==========
    state Deployment as "Deployment" {
        [*] --> NotStarted : "Deploy initialized"
        NotStarted --> CheckingPrereq : "Start"
        CheckingPrereq --> PrereqOK : "All prereq valid"
        CheckingPrereq --> PrereqFailed : "Missing prereq"
        PrereqOK --> InstallingDeps : "Install dependencies"
        PrereqFailed --> [*]: "Abort"
        InstallingDeps --> DepsInstalled : "Deps OK"
        InstallingDeps --> DepsFailed : "Deps failed"
        DepsInstalled --> BuildingDockerImages : "Build Docker"
        DepsFailed --> [*]: "Abort"
        BuildingDockerImages --> ImagesBuilt : "Built"
        BuildingDockerImages --> BuildFailed : "Build failed"
        ImagesBuilt --> StartingServices : "Start svcs"
        BuildFailed --> [*]: "Abort"
        StartingServices --> ServicesStarted : "Services started"
        StartingServices --> ServicesFailed : "Start failed"
        ServicesStarted --> VerifyingHealth : "Health check"
        ServicesFailed --> [*]: "Abort"
        VerifyingHealth --> HealthOK : "OK"
        VerifyingHealth --> HealthFailed : "Failed"
        HealthOK --> Deployed : "Deployed"
        HealthFailed --> Retrying : "Retry"
        Retrying --> StartingServices : "Retry startup"
        Retrying --> [*]: "Max retries"
        Deployed --> [*]: "Success"
    }
    class Deployment,NotStarted,CheckingPrereq,PrereqOK,InstallingDeps,DepsInstalled,BuildingDockerImages,ImagesBuilt,StartingServices,ServicesStarted,VerifyingHealth,HealthOK,Deployed pipeline
    class PrereqFailed,DepsFailed,BuildFailed,ServicesFailed,HealthFailed,Retrying fatal

    %%========== DOCKER SERVICE STATES ==========
    state DockerServices as "Docker Services" {
        [*] --> DSNotCreated : "Service fresh"
        DSNotCreated --> DSCreating : "Create container"
        DSCreating --> DSCreated : "Created"
        DSCreating --> DSCreateFail : "Create failed"
        DSCreated --> DSStarting : "Start"
        DSStarting --> DSRunning : "Running"
        DSStarting --> DSStartFail : "Start failed"
        DSRunning --> DSHealthy : "Health OK"
        DSRunning --> DSUnhealthy : "Health NG"
        DSRunning --> DSStopping : "Stop command"
        DSHealthy --> DSRunning : "Cycle"
        DSUnhealthy --> DSRestarting : "Restart auto"
        DSUnhealthy --> DSStopping : "Manual stop"
        DSRestarting --> DSStarting : "New start"
        DSRestarting --> DSRestartFail : "Restart failed"
        DSStopping --> DSStopped : "Stopped"
        DSStopped --> DSRemoving : "Remove"
        DSRemoving --> [*]: "Removed"
        DSCreateFail --> [*]: "Abort"
        DSStartFail --> [*]: "Abort"
        DSRestartFail --> [*]: "Abort"
    }
    class DockerServices,DSNotCreated,DSCreating,DSCreated,DSStarting,DSRunning,DSHealthy,DSStopped,DSRemoving docker
    class DSUnhealthy,DSRestarting degraded
    class DSCreateFail,DSStartFail,DSRestartFail,fatal fatal
    class DSStopping stopping

    %%=========== SUPERVISOR STOP ==========
    Stopped: System stopped
    [*] --> Stopped : "Hard exit"
    class Stopped stopping

    %%====== LEGEND (simulate with note) ======
    note right of WaitUser
      <b>Color Legend:</b><br>
      <span style="color:#2986cc;">Blue = User states</span><br>
      <span style="color:#48b96a;">Green = Healthy/success</span><br>
      <span style="color:#cba600;">Yellow = Degraded/recovery</span><br>
      <span style="color:#f89c17;">Orange = Pipeline/deployment</span><br>
      <span style="color:#888;">Grey = Docker general or stopped</span><br>
      <span style="color:#f44336;">Red = Fatal/irreversible</span>
    end note
```
