"""Tests for structured logging configuration."""

import logging
import logging.handlers

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


def test_json_format_selects_json_renderer():
    configure_logging(Settings(LOG_FORMAT="json", _env_file=None))
    cfg = structlog.get_config()
    assert any(isinstance(p, structlog.processors.JSONRenderer) for p in cfg["processors"])
    assert isinstance(cfg["logger_factory"], structlog.PrintLoggerFactory)
    _reset_structlog()


def test_log_file_wires_rotating_file_handler(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_file = tmp_path / "backend.log"
    root_handlers = list(logging.getLogger().handlers)
    try:
        configure_logging(Settings(LOG_FORMAT="json", LOG_FILE=str(log_file), _env_file=None))
        cfg = structlog.get_config()
        assert any(p is structlog.stdlib.ProcessorFormatter.wrap_for_formatter for p in cfg["processors"])
        assert isinstance(cfg["logger_factory"], structlog.stdlib.LoggerFactory)

        root = logging.getLogger()
        file_handlers = [h for h in root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert file_handlers, "expected a RotatingFileHandler on the root logger"
        assert file_handlers[0].baseFilename == str(log_file)
        assert isinstance(file_handlers[0].formatter, structlog.stdlib.ProcessorFormatter)
    finally:
        logger = logging.getLogger()
        logger.handlers[:] = root_handlers
        _reset_structlog()
