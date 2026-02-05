# Architecture IDS2 - Diagrammes Mermaid

## Architecture Système

```mermaid
graph TB
    subgraph "Raspberry Pi Host"
        subgraph "Docker Environment"
            BASE[ids2-python-base<br/>Python 3.12 + Requirements]
            
            subgraph "Core Services"
                RUNTIME[ids-runtime<br/>IDS Agent Supervisor]
                API[ids-api<br/>FastAPI Status API]
            end
            
            subgraph "Data Pipeline"
                VECTOR[vector<br/>Log Collector]
                REDIS[redis<br/>Cache & Buffer]
            end
            
            subgraph "Monitoring Stack"
                PROM[prometheus<br/>Metrics Collection]
                GRAF[grafana<br/>Dashboards]
                CADV[cadvisor<br/>Container Metrics]
                NODE[node_exporter<br/>System Metrics]
            end
        end
        
        subgraph "System Services"
            SURICATA[suricata<br/>IDS Engine]
            SYSTEMD[systemd<br/>Service Manager]
        end
        
        subgraph "Storage"
            RAMDISK[/mnt/ram_logs<br/>RAM Disk]
            LOGS[/var/log/ids<br/>Persistent Logs]
        end
    end
    
    subgraph "External Services"
        AWS[AWS OpenSearch<br/>Log Storage]
        TAILSCALE[Tailscale<br/>VPN Network]
    end
    
    %% Dependencies
    BASE --> RUNTIME
    BASE --> API
    RUNTIME --> API
    SURICATA --> RAMDISK
    RAMDISK --> VECTOR
    VECTOR --> REDIS
    VECTOR --> AWS
    REDIS --> RUNTIME
    RUNTIME --> PROM
    CADV --> PROM
    NODE --> PROM
    PROM --> GRAF
    SYSTEMD --> SURICATA
    SYSTEMD --> RUNTIME
    SYSTEMD --> VECTOR
    SYSTEMD --> REDIS
    
    %% Styling
    classDef docker fill:#e1f5fe
    classDef system fill:#f3e5f5
    classDef storage fill:#e8f5e8
    classDef external fill:#fff3e0
    
    class BASE,RUNTIME,API,VECTOR,REDIS,PROM,GRAF,CADV,NODE docker
    class SURICATA,SYSTEMD system
    class RAMDISK,LOGS storage
    class AWS,TAILSCALE external
```

## Architecture de Classes

```mermaid
classDiagram
    class IDSSupervisor {
        +ConfigLoader config
        +StateManager state
        +ComponentManager components
        +start()
        +stop()
        +restart()
        +get_status()
    }
    
    class ConfigLoader {
        +load_config()
        +validate_config()
        +get_setting(key)
        +reload_config()
    }
    
    class StateManager {
        +current_state: State
        +transition_to(state)
        +get_state()
        +is_valid_transition()
    }
    
    class ComponentManager {
        +SuricataManager suricata
        +VectorManager vector
        +RedisManager redis
        +AWSManager aws
        +start_all()
        +stop_all()
        +health_check()
    }
    
    class SuricataManager {
        +start_suricata()
        +stop_suricata()
        +reload_rules()
        +get_stats()
    }
    
    class VectorManager {
        +start_vector()
        +configure_pipeline()
        +monitor_throughput()
        +adjust_throttling()
    }
    
    class RedisManager {
        +connect()
        +store_metrics()
        +get_cached_data()
        +flush_cache()
    }
    
    class AWSManager {
        +OpenSearchClient client
        +upload_logs()
        +create_index()
        +query_logs()
    }
    
    class FastAPIApp {
        +get_status()
        +get_metrics()
        +get_health()
        +restart_service()
    }
    
    IDSSupervisor --> ConfigLoader
    IDSSupervisor --> StateManager
    IDSSupervisor --> ComponentManager
    ComponentManager --> SuricataManager
    ComponentManager --> VectorManager
    ComponentManager --> RedisManager
    ComponentManager --> AWSManager
    FastAPIApp --> IDSSupervisor
```

## Machine à États (FSM)

```mermaid
stateDiagram-v2
    [*] --> Initializing
    
    Initializing --> ConfigLoading : Load Config
    ConfigLoading --> ConfigError : Config Invalid
    ConfigLoading --> ComponentsStarting : Config Valid
    
    ComponentsStarting --> SuricataStarting : Start Components
    SuricataStarting --> VectorStarting : Suricata OK
    VectorStarting --> RedisStarting : Vector OK
    RedisStarting --> Running : Redis OK
    
    Running --> Monitoring : Normal Operation
    Monitoring --> Running : All OK
    Monitoring --> Degraded : Component Issue
    Monitoring --> Error : Critical Failure
    
    Degraded --> Recovering : Auto Repair
    Recovering --> Running : Repair Success
    Recovering --> Error : Repair Failed
    
    Error --> Restarting : Manual/Auto Restart
    Restarting --> Initializing : Restart Complete
    
    ConfigError --> [*] : Exit
    Error --> [*] : Fatal Error
    
    %% Transitions from any state
    Running --> Stopping : Stop Command
    Degraded --> Stopping : Stop Command
    Monitoring --> Stopping : Stop Command
    
    Stopping --> Stopped : All Stopped
    Stopped --> [*] : Exit
    Stopped --> Initializing : Restart Command
```