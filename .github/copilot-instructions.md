# Copilot instructions for IDS2 (Raspberry Pi SOC)

## Big picture
- IDS2 runs a Pi-hosted IDS pipeline: Suricata writes eve.json to a RAM disk, Vector transforms to ECS and ships to Redis + AWS OpenSearch, with Prometheus/Grafana for observability. See [README.md](README.md).
- The Python agent is the orchestrator. The supervisor in [python_env/main.py](python_env/main.py) spawns multi-process managers and maintains a shared state dict.
- Core managers live in [python_env/modules](python_env/modules) and all inherit `BaseComponent` from [python_env/modules/base_component.py](python_env/modules/base_component.py).

## Runtime flow (agent)
- Startup path in [python_env/main.py](python_env/main.py):
  - Checks Git branch must be `dev` via `GitWorkflow` (see [python_env/modules/git_workflow.py](python_env/modules/git_workflow.py)).
  - Generates config files with `VectorManager.generate_vector_config()` and `SuricataManager.generate_suricata_config()` (see [python_env/modules/vector_manager.py](python_env/modules/vector_manager.py), [python_env/modules/suricata_manager.py](python_env/modules/suricata_manager.py)).
  - Starts Suricata on the host, then brings up Docker Compose and waits for health.
  - Spawns `ResourceController`, `MetricsServer`, `ConnectivityAsync`, `SuricataRulesManager`, `WebInterfaceManager` processes.
- Shared state keys (`cpu_usage`, `ram_usage`, `docker_healthy`, `aws_ready`, etc.) are the cross-process contract; update via `BaseComponent.update_shared_state()`.

## Configuration and generated artifacts
- Primary config is [config.yaml](config.yaml). Manager classes read via `ConfigManager.get()` (see [python_env/modules/config_manager.py](python_env/modules/config_manager.py)).
- Vector config is generated into [vector/vector.toml](vector/vector.toml) and Suricata config into [suricata/suricata.yaml](suricata/suricata.yaml); do not hand-edit unless you also update the generators.
- Logs are written to the RAM disk at /mnt/ram_logs (see [config.yaml](config.yaml) and [deploy/install.sh](deploy/install.sh)).

## Services and infrastructure
- Docker services (Vector, Redis, Prometheus, Grafana, cAdvisor, node_exporter) are defined in [docker/docker-compose.yml](docker/docker-compose.yml).
- Systemd units are in [deploy/ids2-agent.service](deploy/ids2-agent.service) and [deploy/suricata.service](deploy/suricata.service). Start/stop via [deploy/start_agent.sh](deploy/start_agent.sh) and [deploy/stop_agent.sh](deploy/stop_agent.sh).
- AWS/OpenSearch integration uses SigV4 in `AWSManager` (see [python_env/modules/aws_manager.py](python_env/modules/aws_manager.py)).

## Local developer workflows
- Python env setup: [setup_venv.sh](setup_venv.sh) (creates python_env/venv and installs [python_env/requirements.txt](python_env/requirements.txt)).
- Full device install: [deploy/install.sh](deploy/install.sh) (system deps, Docker, Suricata, RAM disk, systemd services).
- The agent is typically run via systemd, not by direct CLI; if you do run it manually, use [python_env/main.py](python_env/main.py).

## Project-specific patterns
- Managers are long-running loops; honor `shutdown_event` and use `BaseComponent.is_shutdown_requested()`.
- Resource throttling is driven by `ResourceController` thresholds in [config.yaml](config.yaml); other components should read `throttling_level` from shared state rather than invent their own.
- Connectivity checks are async with uvloop and update `aws_ready`/`redis_ready`/`pipeline_ok` in shared state (see [python_env/modules/connectivity_async.py](python_env/modules/connectivity_async.py)).
- Web UI expects files under web_interface/ (mounted in `WebInterfaceManager`), but those files are not present in the repo; confirm before relying on UI assets.
