"""
FastAPI dashboard application for IDS monitoring.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .ai_healing import AIHealingService
from .elasticsearch import ElasticsearchMonitor
from .hardware import HardwareController
from ids.domain import (
    AIHealingResponse,
    ElasticsearchHealth,
    MirrorStatus,
    NetworkStats,
    PipelineStatus,
    SystemHealth,
    TailscaleNode,
)
from .mirroring import MirrorMonitor
from .network import NetworkMonitor
from .setup import OpenSearchSetup, TailnetSetup, setup_infrastructure
from .suricata import SuricataLogMonitor
from .tailscale import TailscaleMonitor
from ids.storage import crud, get_session, init_db, models, schemas
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Global state
dashboard_state: dict[str, Any] = {}


def _schema_from_model(schema_cls, instance):
    data = {field: getattr(instance, field) for field in schema_cls.model_fields}
    return schema_cls(**data)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    logger.info("Starting IDS Dashboard...")

    # Initialize database
    init_db()
    seed_db = next(get_session())
    for model in (
        models.Secrets,
        models.AwsConfig,
        models.RaspberryPiConfig,
        models.SuricataConfig,
        models.VectorConfig,
        models.TailscaleConfig,
        models.FastapiConfig,
    ):
        crud.get_or_create_singleton(seed_db, model)
    seed_db.close()

    # Initialize components
    dashboard_state["startup_issues"] = []
    dashboard_state["ai_healing"] = AIHealingService(api_key=os.getenv("ANTHROPIC_API_KEY"))

    async def record_startup_issue(component: str, error: Exception) -> None:
        ai_healing = dashboard_state.get("ai_healing")
        if ai_healing:
            response = await ai_healing.handle_pipeline_error(component, error)
        else:
            response = AIHealingResponse(
                error_type=f"{component.capitalize()}Error",
                error_message=str(error),
                suggestion="AI healing service not available. Install anthropic package.",
                timestamp=datetime.now(),
            )
        dashboard_state["startup_issues"].append(response)

    db = next(get_session())
    suricata_cfg = crud.get_or_create_singleton(db, models.SuricataConfig)
    pi_cfg = crud.get_or_create_singleton(db, models.RaspberryPiConfig)
    db.close()

    try:
        dashboard_state["suricata"] = SuricataLogMonitor(log_path=Path(suricata_cfg.log_path))
        await dashboard_state["suricata"].start()
    except Exception as exc:
        logger.error(f"Failed to start Suricata monitor: {exc}")
        await record_startup_issue("suricata", exc)

    try:
        dashboard_state["elasticsearch"] = ElasticsearchMonitor(
            hosts=os.getenv("ELASTICSEARCH_HOSTS", "http://localhost:9200").split(","),
            username=os.getenv("ELASTICSEARCH_USERNAME"),
            password=os.getenv("ELASTICSEARCH_PASSWORD"),
        )
        await dashboard_state["elasticsearch"].connect()
    except Exception as exc:
        logger.error(f"Failed to connect to Elasticsearch: {exc}")
        await record_startup_issue("elasticsearch", exc)

    try:
        mirror_interface = pi_cfg.network_interface or os.getenv("MIRROR_INTERFACE", "eth0")
        dashboard_state["network"] = NetworkMonitor(interface=mirror_interface)
        promisc_enabled = await dashboard_state["network"].ensure_promiscuous_mode()
        if not promisc_enabled:
            await record_startup_issue(
                "network",
                RuntimeError("Failed to enable promiscuous mode on mirror interface."),
            )
    except Exception as exc:
        logger.error(f"Failed to initialize network monitor: {exc}")
        await record_startup_issue("network", exc)

    try:
        dashboard_state["hardware"] = HardwareController(led_pin=int(os.getenv("LED_PIN", "17")))
    except Exception as exc:
        logger.error(f"Failed to initialize hardware controller: {exc}")
        await record_startup_issue("hardware", exc)

    tailnet = os.getenv("TAILSCALE_TAILNET")
    tailscale_api_key = os.getenv("TAILSCALE_API_KEY")
    if tailnet and tailscale_api_key:
        try:
            dashboard_state["tailscale"] = TailscaleMonitor(
                tailnet=tailnet,
                api_key=tailscale_api_key,
            )
        except Exception as exc:
            logger.error(f"Failed to initialize Tailscale monitor: {exc}")
            dashboard_state["tailscale"] = None
            await record_startup_issue("tailscale", exc)
    else:
        dashboard_state["tailscale"] = None

    mirror_monitor = MirrorMonitor(
        base_url=os.getenv("TP_LINK_SWITCH_URL"),
        username=os.getenv("TP_LINK_SWITCH_USER"),
        password=os.getenv("TP_LINK_SWITCH_PASSWORD"),
        source_port=os.getenv("TP_LINK_MIRROR_SOURCE", "1"),
        mirror_port=os.getenv("TP_LINK_MIRROR_TARGET", "5"),
    )
    try:
        dashboard_state["mirror_monitor"] = mirror_monitor
        mirror_status = await mirror_monitor.check_mirroring()
        dashboard_state["mirror_status"] = mirror_status
        if mirror_status.configured and not mirror_status.active:
            await record_startup_issue(
                "mirroring",
                RuntimeError("Port mirroring inactive on TP-Link switch."),
            )
    except Exception as exc:
        logger.error(f"Failed to verify mirroring configuration: {exc}")
        dashboard_state["mirror_status"] = MirrorStatus(
            configured=True,
            active=False,
            source_port=os.getenv("TP_LINK_MIRROR_SOURCE", "1"),
            mirror_port=os.getenv("TP_LINK_MIRROR_TARGET", "5"),
            message=str(exc),
            checked_at=datetime.now(),
        )
        await record_startup_issue("mirroring", exc)

    logger.info("IDS Dashboard started")

    yield

    # Shutdown
    logger.info("Shutting down IDS Dashboard...")

    if "suricata" in dashboard_state:
        await dashboard_state["suricata"].stop()

    if "elasticsearch" in dashboard_state:
        await dashboard_state["elasticsearch"].disconnect()

    if "hardware" in dashboard_state:
        dashboard_state["hardware"].cleanup()

    logger.info("IDS Dashboard stopped")


def create_dashboard_app() -> FastAPI:
    """Create and configure the FastAPI dashboard application."""
    app = FastAPI(
        title="IDS Dashboard",
        description="Professional monitoring dashboard for Raspberry Pi IDS",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify allowed origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # WebSocket endpoint for real-time alerts
    @app.websocket("/ws/alerts")
    async def websocket_alerts(websocket: WebSocket):
        """WebSocket endpoint for streaming Suricata alerts."""
        await websocket.accept()
        logger.info("WebSocket client connected for alerts")

        suricata = dashboard_state.get("suricata")
        hardware = dashboard_state.get("hardware")

        if not suricata:
            await websocket.send_json({"error": "Suricata monitor not available"})
            await websocket.close()
            return

        try:
            async for alert in suricata.tail_alerts():
                # Flash LED for critical alerts
                if hardware and alert.severity == 1:
                    hardware.handle_alert(alert.severity)

                # Send alert to client
                await websocket.send_json(alert.model_dump(mode="json"))

        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await websocket.close()

    # REST API endpoints
    @app.get("/api/alerts/recent")
    async def get_recent_alerts(limit: int = 100) -> list[dict]:
        """Get recent Suricata alerts."""
        suricata = dashboard_state.get("suricata")
        if not suricata:
            return []

        alerts = await suricata.get_recent_alerts(limit=limit)
        return [alert.model_dump(mode="json") for alert in alerts]

    @app.get("/api/elasticsearch/health")
    async def get_elasticsearch_health() -> ElasticsearchHealth | None:
        """Get Elasticsearch cluster health."""
        es = dashboard_state.get("elasticsearch")
        if not es:
            return None

        return await es.get_cluster_health()

    @app.get("/api/network/stats")
    async def get_network_stats() -> NetworkStats | None:
        """Get network interface statistics."""
        network = dashboard_state.get("network")
        if not network:
            return None

        return await network.get_interface_stats()

    @app.get("/api/system/health")
    async def get_system_health() -> SystemHealth:
        """Get Raspberry Pi system health metrics."""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # Get CPU temperature (Raspberry Pi)
        temperature = None
        try:
            temp_file = Path("/sys/class/thermal/thermal_zone0/temp")
            if temp_file.exists():
                temp_raw = temp_file.read_text().strip()
                temperature = float(temp_raw) / 1000.0  # Convert from millidegrees
        except Exception:
            pass

        boot_time = psutil.boot_time()
        import time

        uptime = time.time() - boot_time

        return SystemHealth(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used=memory.used,
            memory_total=memory.total,
            disk_percent=disk.percent,
            disk_used=disk.used,
            disk_total=disk.total,
            temperature=temperature,
            uptime=uptime,
            timestamp=datetime.now(),
        )

    @app.get("/api/db/health")
    async def get_db_health() -> dict[str, str]:
        """Check database connectivity."""
        session = None
        try:
            session = next(get_session())
            session.execute(text("SELECT 1"))
            return {"status": "ok"}
        except Exception as exc:  # pragma: no cover - health check
            return {"status": "error", "detail": str(exc)}
        finally:
            if session is not None:
                session.close()

    @app.get("/api/pipeline/status")
    async def get_pipeline_status() -> PipelineStatus:
        """Get pipeline component status."""

        # Check Suricata
        suricata_status = "unknown"
        try:
            result = await asyncio.to_thread(
                lambda: __import__("subprocess").run(
                    ["systemctl", "is-active", "suricata"],
                    capture_output=True,
                    text=True,
                )
            )
            suricata_status = "running" if result.returncode == 0 else "stopped"
        except Exception:
            suricata_status = "error"

        # Check Vector
        vector_status = "unknown"
        try:
            result = await asyncio.to_thread(
                lambda: __import__("subprocess").run(
                    ["systemctl", "is-active", "vector"],
                    capture_output=True,
                    text=True,
                )
            )
            vector_status = "running" if result.returncode == 0 else "stopped"
        except Exception:
            vector_status = "error"

        # Check Elasticsearch
        es = dashboard_state.get("elasticsearch")
        es_status = "unavailable"
        if es:
            health = await es.get_cluster_health()
            if health:
                es_status = health.status

        db = next(get_session())
        pi_config = crud.get_or_create_singleton(db, models.RaspberryPiConfig)
        db.close()
        return PipelineStatus(
            interface=pi_config.network_interface or os.getenv("MIRROR_INTERFACE", "eth0"),
            suricata=suricata_status,
            vector=vector_status,
            elasticsearch=es_status,
            timestamp=datetime.now(),
        )

    @app.get("/api/tailscale/nodes")
    async def get_tailscale_nodes() -> list[TailscaleNode]:
        """Get Tailscale tailnet nodes."""
        tailscale = dashboard_state.get("tailscale")
        if not tailscale:
            return []

        return await tailscale.get_nodes()

    @app.get("/api/config/secrets")
    async def get_secrets_config(db: Session = Depends(get_session)) -> schemas.SecretsSchema:
        secrets = crud.get_or_create_singleton(db, models.Secrets)
        return _schema_from_model(schemas.SecretsSchema, secrets)

    @app.put("/api/config/secrets")
    async def update_secrets_config(
        payload: schemas.SecretsSchema,
        db: Session = Depends(get_session),
    ) -> schemas.SecretsSchema:
        secrets = crud.get_or_create_singleton(db, models.Secrets)
        crud.update_model(secrets, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(secrets)
        return _schema_from_model(schemas.SecretsSchema, secrets)

    @app.get("/api/config/aws")
    async def get_aws_config(db: Session = Depends(get_session)) -> schemas.AwsConfigSchema:
        config = crud.get_or_create_singleton(db, models.AwsConfig)
        return _schema_from_model(schemas.AwsConfigSchema, config)

    @app.put("/api/config/aws")
    async def update_aws_config(
        payload: schemas.AwsConfigSchema,
        db: Session = Depends(get_session),
    ) -> schemas.AwsConfigSchema:
        config = crud.get_or_create_singleton(db, models.AwsConfig)
        crud.update_model(config, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(config)
        return _schema_from_model(schemas.AwsConfigSchema, config)

    @app.get("/api/config/raspberry-pi")
    async def get_pi_config(
        db: Session = Depends(get_session),
    ) -> schemas.RaspberryPiConfigSchema:
        config = crud.get_or_create_singleton(db, models.RaspberryPiConfig)
        return _schema_from_model(schemas.RaspberryPiConfigSchema, config)

    @app.put("/api/config/raspberry-pi")
    async def update_pi_config(
        payload: schemas.RaspberryPiConfigSchema,
        db: Session = Depends(get_session),
    ) -> schemas.RaspberryPiConfigSchema:
        config = crud.get_or_create_singleton(db, models.RaspberryPiConfig)
        crud.update_model(config, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(config)
        return _schema_from_model(schemas.RaspberryPiConfigSchema, config)

    @app.get("/api/config/suricata")
    async def get_suricata_config(
        db: Session = Depends(get_session),
    ) -> schemas.SuricataConfigSchema:
        config = crud.get_or_create_singleton(db, models.SuricataConfig)
        return _schema_from_model(schemas.SuricataConfigSchema, config)

    @app.put("/api/config/suricata")
    async def update_suricata_config(
        payload: schemas.SuricataConfigSchema,
        db: Session = Depends(get_session),
    ) -> schemas.SuricataConfigSchema:
        config = crud.get_or_create_singleton(db, models.SuricataConfig)
        crud.update_model(config, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(config)
        return _schema_from_model(schemas.SuricataConfigSchema, config)

    @app.get("/api/config/vector")
    async def get_vector_config(db: Session = Depends(get_session)) -> schemas.VectorConfigSchema:
        config = crud.get_or_create_singleton(db, models.VectorConfig)
        return _schema_from_model(schemas.VectorConfigSchema, config)

    @app.put("/api/config/vector")
    async def update_vector_config(
        payload: schemas.VectorConfigSchema,
        db: Session = Depends(get_session),
    ) -> schemas.VectorConfigSchema:
        config = crud.get_or_create_singleton(db, models.VectorConfig)
        crud.update_model(config, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(config)
        return _schema_from_model(schemas.VectorConfigSchema, config)

    @app.get("/api/config/tailscale")
    async def get_tailscale_config(
        db: Session = Depends(get_session),
    ) -> schemas.TailscaleConfigSchema:
        config = crud.get_or_create_singleton(db, models.TailscaleConfig)
        return _schema_from_model(schemas.TailscaleConfigSchema, config)

    @app.put("/api/config/tailscale")
    async def update_tailscale_config(
        payload: schemas.TailscaleConfigSchema,
        db: Session = Depends(get_session),
    ) -> schemas.TailscaleConfigSchema:
        config = crud.get_or_create_singleton(db, models.TailscaleConfig)
        crud.update_model(config, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(config)
        return _schema_from_model(schemas.TailscaleConfigSchema, config)

    @app.get("/api/config/fastapi")
    async def get_fastapi_config(
        db: Session = Depends(get_session),
    ) -> schemas.FastapiConfigSchema:
        config = crud.get_or_create_singleton(db, models.FastapiConfig)
        return _schema_from_model(schemas.FastapiConfigSchema, config)

    @app.put("/api/config/fastapi")
    async def update_fastapi_config(
        payload: schemas.FastapiConfigSchema,
        db: Session = Depends(get_session),
    ) -> schemas.FastapiConfigSchema:
        config = crud.get_or_create_singleton(db, models.FastapiConfig)
        crud.update_model(config, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(config)
        return _schema_from_model(schemas.FastapiConfigSchema, config)

    @app.get("/api/systemd/services")
    async def list_systemd_services() -> list[dict]:
        """List systemd services and status."""
        services = ["suricata", "vector", "ids-dashboard", "docker", "tailscaled"]
        results = []
        for service in services:
            try:
                result = await asyncio.to_thread(
                    lambda: __import__("subprocess").run(
                        ["systemctl", "is-active", service],
                        capture_output=True,
                        text=True,
                    )
                )
                status = result.stdout.strip() or "unknown"
            except Exception:
                status = "unknown"
            results.append({"service": service, "status": status})
        return results

    @app.post("/api/ai-healing/diagnose")
    async def diagnose_error(
        error_type: str,
        error_message: str,
        component: str | None = None,
    ) -> dict:
        """Diagnose an error using AI healing."""
        ai_healing = dashboard_state.get("ai_healing")
        if not ai_healing:
            return {"error": "AI healing service not available"}

        response = await ai_healing.diagnose_error(
            error_type=error_type,
            error_message=error_message,
            context={"component": component} if component else None,
        )

        return response.model_dump(mode="json")

    @app.get("/api/ai-healing/startup-issues")
    async def get_startup_issues() -> list[dict]:
        """Get AI healing suggestions captured during startup."""
        issues: list[AIHealingResponse] = dashboard_state.get("startup_issues", [])
        return [issue.model_dump(mode="json") for issue in issues]

    @app.get("/api/mirror/status")
    async def get_mirror_status() -> MirrorStatus | None:
        """Get port mirroring verification status."""
        mirror_monitor = dashboard_state.get("mirror_monitor")
        if mirror_monitor:
            dashboard_state["mirror_status"] = await mirror_monitor.check_mirroring()
        return dashboard_state.get("mirror_status")

    # ============================================================================
    # Setup & Configuration Endpoints
    # ============================================================================

    @app.get("/api/setup/tailnet/verify")
    async def verify_tailnet(db: Session = Depends(get_session)) -> dict:
        """Verify Tailscale tailnet configuration."""
        setup = TailnetSetup(session=db)
        return await setup.verify_tailnet()

    @app.post("/api/setup/tailnet/create-key")
    async def create_tailnet_key(
        reusable: bool = True,
        ephemeral: bool = False,
        tags: list[str] | None = None,
        db: Session = Depends(get_session),
    ) -> dict:
        """Create a Tailscale auth key."""
        setup = TailnetSetup(session=db)
        return await setup.create_auth_key(reusable=reusable, ephemeral=ephemeral, tags=tags)

    @app.get("/api/setup/opensearch/verify")
    async def verify_opensearch(
        domain_name: str | None = None,
        db: Session = Depends(get_session),
    ) -> dict:
        """Verify OpenSearch domain configuration."""
        setup = OpenSearchSetup(Path("config.yaml"), session=db)
        return await setup.verify_domain(domain_name)

    @app.post("/api/setup/opensearch/create")
    async def create_opensearch_domain(
        domain_name: str | None = None,
        wait: bool = True,
        timeout: int = 1800,
        db: Session = Depends(get_session),
    ) -> dict:
        """Create OpenSearch domain."""
        setup = OpenSearchSetup(Path("config.yaml"), session=db)
        return await setup.create_domain(domain_name=domain_name, wait=wait, timeout=timeout)

    @app.post("/api/setup/infrastructure")
    async def setup_complete_infrastructure(
        tailnet: str | None = None,
        tailscale_api_key: str | None = None,
        opensearch_domain: str | None = None,
    ) -> dict:
        """
        Setup complete infrastructure (Tailnet + OpenSearch).

        This endpoint will:
        - Verify or configure Tailscale tailnet
        - Create or verify OpenSearch domain
        """
        # Use env vars if not provided
        tailnet = tailnet or os.getenv("TAILSCALE_TAILNET")
        tailscale_api_key = tailscale_api_key or os.getenv("TAILSCALE_API_KEY")
        opensearch_domain = opensearch_domain or os.getenv("OPENSEARCH_DOMAIN_NAME")

        config_path = Path("config.yaml")

        return await setup_infrastructure(
            tailnet=tailnet,
            tailscale_api_key=tailscale_api_key,
            opensearch_domain=opensearch_domain,
            config_path=config_path,
        )

    @app.post("/api/setup/first-run")
    async def run_first_access_deployment(db: Session = Depends(get_session)) -> dict:
        """Run the first access deployment workflow."""
        deployment = models.DeploymentHistory(
            deployment_type="initial",
            component="all",
            status="in_progress",
        )
        db.add(deployment)
        db.commit()
        db.refresh(deployment)

        steps = []

        async def run_step(name: str, coro):
            try:
                result = await coro
                steps.append({"step": name, "status": "success", "result": result})
                return True
            except Exception as exc:
                steps.append({"step": name, "status": "failed", "error": str(exc)})
                return False

        tailnet_setup = TailnetSetup(session=db)
        opensearch_setup = OpenSearchSetup(Path("config.yaml"), session=db)

        await run_step("tailscale_verify", tailnet_setup.verify_tailnet())
        await run_step("opensearch_verify", opensearch_setup.verify_domain(None))

        async def start_service(service: str):
            await asyncio.to_thread(
                lambda: __import__("subprocess").run(
                    ["systemctl", "start", service],
                    capture_output=True,
                    text=True,
                )
            )

        await run_step("start_suricata", start_service("suricata"))
        await run_step("start_vector", start_service("vector"))
        await run_step("start_dashboard", start_service("ids-dashboard"))

        deployment.status = "success" if all(step["status"] == "success" for step in steps) else "failed"
        deployment.completed_at = datetime.now()
        db.commit()

        return {"deployment_id": deployment.id, "steps": steps, "status": deployment.status}

    # Serve static frontend (if available)
    frontend_path = Path(__file__).resolve().parents[4] / "frontend" / "dist"
    if frontend_path.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

        @app.get("/", response_class=HTMLResponse)
        async def serve_frontend():
            """Serve the frontend application."""
            index_file = frontend_path / "index.html"
            if index_file.exists():
                return index_file.read_text()
            return "<html><body><h1>IDS Dashboard</h1><p>Frontend not built. Run 'npm run build' in frontend directory.</p></body></html>"

    return app


# Create app instance
app = create_dashboard_app()
