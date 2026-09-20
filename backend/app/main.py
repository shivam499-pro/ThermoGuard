"""
ThermoGuard FastAPI application entry point.

Responsibilities:
  - Create and configure the FastAPI application instance.
  - Register global exception handlers.
  - Mount the /health endpoint directly (no AWS, no Bedrock, no frontend).
  - Provide a factory function (create_app) for testability.

Future commits will attach domain routers (risk engine, analysis API, etc.)
via app.include_router(...) without modifying this module's core structure.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.observability import configure_logging
from app.schemas import HealthResponse
from app.api.events import router as events_router
from app.api.jobs import router as jobs_router

# ── Logging setup ─────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)


# ── Application factory ───────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """
    Construct and configure the ThermoGuard FastAPI application.

    Returns a fully configured app instance suitable for both production
    (via uvicorn) and test usage (via TestClient).
    """
    settings = get_settings()
    if settings.json_logs:
        configure_logging(settings.log_level)
    else:
        logging.basicConfig(level=settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Satellite-driven thermal anomaly detection and industrial fire "
            "classification using deterministic risk assessment."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global exception handlers ─────────────────────────────────────────────

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """Return a structured 422 response for domain-level validation errors."""
        logger.warning("ValueError on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc), "type": "validation_error"},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Catch-all handler — return 500 without leaking internal details.
        Log the full exception for debugging.
        """
        logger.exception("Unhandled exception on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "type": "server_error"},
        )

    # ── Domain routers ─────────────────────────────────────────────────────
    app.include_router(events_router, prefix=settings.api_prefix)
    app.include_router(jobs_router, prefix=settings.api_prefix)

    # ── Routes ────────────────────────────────────────────────────────────────

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="Health check",
        tags=["System"],
    )
    async def health() -> HealthResponse:
        """
        Liveness probe.

        Returns HTTP 200 with application name and version when the service
        is running correctly. No external dependencies are checked here.
        """
        return HealthResponse(
            status="ok",
            version=settings.app_version,
            service=settings.app_name,
        )

    logger.info(
        "ThermoGuard backend initialised (version=%s, debug=%s)",
        settings.app_version,
        settings.debug,
    )

    return app


# ── Application instance ──────────────────────────────────────────────────────
# Uvicorn / ASGI server entry point: `uvicorn app.main:app`

app = create_app()

# API Gateway + Lambda ingress adapter (Mangum). Local uvicorn ignores this.
try:
    from mangum import Mangum

    handler = Mangum(app, lifespan="off")
except ImportError:  # pragma: no cover - local pytest without mangum is fine
    handler = None
