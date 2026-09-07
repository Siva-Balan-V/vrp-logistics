from __future__ import annotations

import logging
import logging.handlers

import structlog

from app.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure structlog + stdlib logging from app settings.

    - ``LOG_FORMAT=json`` emits JSON to stdout; ``console`` uses the dev renderer.
    - ``LOG_FILE`` (rotated, 10 MB x 5) redirects output to a file instead.
    - ``LOG_LEVEL`` maps to the structlog filtering bound logger.
    """
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
