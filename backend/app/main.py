from __future__ import annotations

import time
import logging

import structlog
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models.schemas import HealthResponse
from app.routes.optimization import router as opt_router
from app.services.cache import init_cache

# ─────────────────────────────────────────────
# Structured logging setup
# ─────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger(__name__)
settings = get_settings()

# ─────────────────────────────────────────────
# App factory
# ─────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Last-Mile Logistics Vehicle Routing Optimization API. "
            "Handles 600+ delivery locations across 18+ vehicles with real road-network distances."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request timing middleware ─────────────────────────────────────────────
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start = time.perf_counter()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            path=request.url.path,
            method=request.method,
        )
        response = await call_next(request)
        elapsed = round((time.perf_counter() - start) * 1000, 1)
        response.headers["X-Process-Time-Ms"] = str(elapsed)
        logger.info("request", status=response.status_code, ms=elapsed)
        return response

    # ── Global exception handler ──────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("unhandled_exception", error=str(exc), path=request.url.path, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Internal server error", "detail": str(exc)},
        )

    # ── Startup ───────────────────────────────────────────────────────────────
    @app.on_event("startup")
    async def startup():
        init_cache(settings.REDIS_URL)
        logger.info(
            "app_started",
            name=settings.APP_NAME,
            version=settings.APP_VERSION,
            routing_backend=settings.ROUTING_BACKEND,
        )

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    async def health():
        return HealthResponse(
            status="ok",
            version=settings.APP_VERSION,
            routing_backend=settings.ROUTING_BACKEND,
        )

    @app.get("/", tags=["meta"])
    async def root():
        return {"message": "VRP Logistics Optimizer API", "docs": "/docs"}

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(opt_router)

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
