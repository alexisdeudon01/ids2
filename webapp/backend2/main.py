"""Minimal FastAPI app matching frontend requirements."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.system_health import router as system_router
from api.db_health import router as db_router


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
    
    return app


app = create_app()
