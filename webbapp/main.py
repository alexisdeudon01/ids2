"""Minimal FastAPI app matching frontend requirements."""

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from api.system_health import router as system_router
from api.db_health import router as db_router
from api.alerts import router as alerts_router
from api.network import router as network_router
from api.pipeline import router as pipeline_router
from api.costs import router as costs_router


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="IDS Dashboard API",
        description="Minimal API for frontend dashboard",
        version="1.0.0",
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(system_router)
    app.include_router(db_router)
    app.include_router(alerts_router)
    app.include_router(network_router)
    app.include_router(pipeline_router)
    app.include_router(costs_router)
    
    # Serve frontend if built
    frontend_dist = Path(__file__).parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

        @app.get("/{path:path}")
        async def serve_frontend(path: str):
            index_file = frontend_dist / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            return "Frontend not built"
    
    return app


app = create_app()
