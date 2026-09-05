"""Tests for application configuration."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_defaults():
    """Settings should have sensible defaults (no .env file)."""
    settings = Settings(_env_file=None)
    assert settings.APP_NAME == "VRP Logistics Optimizer"
    assert settings.APP_VERSION == "1.0.0"
    assert settings.DEBUG is False
    assert settings.ROUTING_BACKEND == "haversine"
    assert settings.REDIS_URL is None
    assert settings.SOLVER_TIME_LIMIT_SECONDS == 60
    assert settings.DEFAULT_MAX_VEHICLES == 18
    assert settings.DEFAULT_VEHICLE_CAPACITY == 50
    assert settings.ALLOWED_ORIGINS == ["http://localhost:5173", "http://localhost:3000"]
    assert settings.OSRM_BATCH_SIZE == 100
    assert settings.ORS_BATCH_SIZE == 50


def test_settings_from_env():
    """Settings should load from environment variables."""
    env_vars = {
        "APP_NAME": "Test App",
        "APP_VERSION": "2.0.0",
        "DEBUG": "true",
        "ROUTING_BACKEND": "osrm",
        "REDIS_URL": "redis://localhost:6379/0",
        "SOLVER_TIME_LIMIT_SECONDS": "120",
        "DEFAULT_MAX_VEHICLES": "50",
        "DEFAULT_VEHICLE_CAPACITY": "100",
        "ALLOWED_ORIGINS": '["http://example.com"]',
        "OSRM_BATCH_SIZE": "50",
        "ORS_BATCH_SIZE": "25",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        settings = Settings(_env_file=None)
        assert settings.APP_NAME == "Test App"
        assert settings.APP_VERSION == "2.0.0"
        assert settings.DEBUG is True
        assert settings.ROUTING_BACKEND == "osrm"
        assert settings.REDIS_URL == "redis://localhost:6379/0"
        assert settings.SOLVER_TIME_LIMIT_SECONDS == 120
        assert settings.DEFAULT_MAX_VEHICLES == 50
        assert settings.DEFAULT_VEHICLE_CAPACITY == 100
        assert settings.ALLOWED_ORIGINS == ["http://example.com"]
        assert settings.OSRM_BATCH_SIZE == 50
        assert settings.ORS_BATCH_SIZE == 25


def test_settings_allowed_origins_parsing():
    """ALLOWED_ORIGINS should parse JSON array from env."""
    with patch.dict(os.environ, {"ALLOWED_ORIGINS": '["http://a.com", "http://b.com"]'}, clear=True):
        settings = Settings(_env_file=None)
        assert len(settings.ALLOWED_ORIGINS) == 2
        assert "http://a.com" in settings.ALLOWED_ORIGINS
        assert "http://b.com" in settings.ALLOWED_ORIGINS


def test_settings_rejects_invalid_routing_backend():
    """ROUTING_BACKEND is an enum — unknown values should fail fast."""
    with patch.dict(os.environ, {"ROUTING_BACKEND": "google-maps"}, clear=True), pytest.raises(ValidationError):
        Settings(_env_file=None)
