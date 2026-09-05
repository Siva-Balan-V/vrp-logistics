"""Tests for OpenTelemetry tracing setup."""

import pytest

import app.tracing


@pytest.fixture(autouse=True)
def reset_tracing_state():
    app.tracing._tracing_enabled = False
    app.tracing._TRACER = None
    yield
    app.tracing._tracing_enabled = False
    app.tracing._TRACER = None


def test_setup_disabled_without_endpoint():
    app.tracing.setup_tracing(otlp_endpoint=None, service_name="vrp-backend")
    assert app.tracing.is_tracing_enabled() is False


def test_setup_disabled_with_empty_endpoint():
    app.tracing.setup_tracing(otlp_endpoint="", service_name="vrp-backend")
    assert app.tracing.is_tracing_enabled() is False
