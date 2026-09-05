"""Tests for structured logging configuration."""

import logging

import structlog

from app.config import Settings
from app.logging_config import configure_logging

_ORIGINAL_PROCESSORS = list(structlog.get_config().get("processors", []))


def _reset_structlog():
    structlog.configure(
        processors=_ORIGINAL_PROCESSORS,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def test_console_format_is_default():
    configure_logging(Settings(LOG_FORMAT="console", _env_file=None))
    cfg = structlog.get_config()
    assert any(isinstance(p, structlog.dev.ConsoleRenderer) for p in cfg["processors"])
    assert isinstance(cfg["logger_factory"], structlog.PrintLoggerFactory)
    _reset_structlog()
