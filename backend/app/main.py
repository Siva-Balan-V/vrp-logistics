from __future__ import annotations

import logging
import logging.handlers
import time
import uuid
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import init_db, wait_for_db
from app.middleware.metrics import MetricsMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.models.schemas import HealthResponse
from app.routes.admin import router as admin_router
from app.routes.analytics import router as analytics_router
from app.routes.auth import router as auth_router
from app.routes.billing import router as billing_router
from app.routes.companies import router as company_router
from app.routes.drivers import router as drivers_router
from app.routes.notifications import router as notifications_router
from app.routes.optimization import router as opt_router
from app.routes.webhooks import router as webhooks_router
from app.services import cache
from app.services.cache import init_cache
from app.websocket_manager import manager

settings = get_settings()

# ─────────────────────────────────────────────
# Structured logging setup
# ─────────────────────────────────────────────
log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

shared_processors = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.stdlib.add_log_level,
]

renderer = structlog.processors.JSONRenderer() if settings.LOG_FORMAT == "json" else structlog.dev.ConsoleRenderer()

if settings.LOG_FILE:
    handler = logging.handlers.RotatingFileHandler(
        settings.LOG_FILE,
        maxBytes=10_485_760,
        backupCount=5,
    )
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=shared_processors + [renderer],
        ),
    )
    logging.basicConfig(handlers=[handler], level=log_level, force=True)
    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
else:
    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────
# App factory
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_cache(settings.REDIS_URL)
    init_db(settings.DATABASE_URL)
    await wait_for_db(settings.DATABASE_URL)
    if not settings.JWT_SECRET_KEY:
        logger.warning("jwt_secret_not_set", detail="JWT_SECRET_KEY is empty — set it in .env for production")
    elif settings.JWT_SECRET_KEY == "CHANGE-ME-IN-PRODUCTION":
        logger.warning(
            "jwt_secret_default", detail="JWT_SECRET_KEY is still the default — change it in .env for production"
        )
    logger.info(
        "app_started",
        name=settings.APP_NAME,
        version=settings.APP_VERSION,
        routing_backend=settings.ROUTING_BACKEND,
    )
    yield


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
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-Process-Time-Ms"],
        max_age=3600,
    )

    # ── Metrics (Prometheus) ────────────────────────────────────────────────
    app.add_middleware(MetricsMiddleware)

    # ── Rate limiting ────────────────────────────────────────────────────────
    app.add_middleware(RateLimitMiddleware)

    # ── Request timing middleware ─────────────────────────────────────────────
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start = time.perf_counter()
        request_id = str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            path=request.url.path,
            method=request.method,
            request_id=request_id,
        )
        response = await call_next(request)
        elapsed = round((time.perf_counter() - start) * 1000, 1)
        response.headers["X-Process-Time-Ms"] = str(elapsed)
        response.headers["X-Request-ID"] = request_id
        logger.info("request", status=response.status_code, ms=elapsed)
        return response

    # ── Global exception handler ──────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("unhandled_exception", error=str(exc), path=request.url.path, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Internal server error"},
        )

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    async def health():
        return HealthResponse(
            status="ok",
            version=settings.APP_VERSION,
            routing_backend=settings.ROUTING_BACKEND,
            redis_connected=cache.is_redis_connected(),
        )

    @app.get("/", tags=["meta"])
    async def root():
        return {"message": "VRP Logistics Optimizer API", "docs": "/docs"}

    # ── WebSocket ─────────────────────────────────────────────────────────────
    from fastapi import Query, WebSocket, WebSocketDisconnect

    @app.websocket("/api/v1/ws/optimization/{run_id}")
    async def ws_optimization(
        ws: WebSocket,
        run_id: str,
        token: str = Query(default=""),
    ):
        if token:
            from app.services.auth import decode_token

            payload = decode_token(token)
            if not payload:
                await ws.close(code=4001)
                return
        await manager.connect(run_id, ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(run_id, ws)
        except Exception:
            manager.disconnect(run_id, ws)

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(auth_router)
    app.include_router(company_router)
    app.include_router(drivers_router)
    app.include_router(opt_router)
    app.include_router(admin_router)
    app.include_router(billing_router)
    app.include_router(webhooks_router)
    app.include_router(notifications_router)
    app.include_router(analytics_router)

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        limit_max_body_size=10_485_760,  # 10 MB
    )
