"""Tests for OpenTelemetry tracing setup."""

from unittest.mock import patch

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


_MOCK_TARGETS = [
    "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter",
    "opentelemetry.sdk.trace.export.BatchSpanProcessor",
    "opentelemetry.sdk.trace.TracerProvider",
    "opentelemetry.sdk.resources.Resource",
]


def test_setup_enabled_with_endpoint():
    with (
        patch("opentelemetry.sdk.resources.Resource.create", return_value="res"),
        patch("opentelemetry.sdk.trace.TracerProvider"),
        patch("opentelemetry.sdk.trace.export.BatchSpanProcessor"),
        patch("opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter"),
        patch("opentelemetry.trace.set_tracer_provider"),
        patch("opentelemetry.trace.get_tracer", return_value="mock-tracer"),
    ):
        app.tracing.setup_tracing(otlp_endpoint="http://localhost:4317", service_name="vrp-backend")
    assert app.tracing.is_tracing_enabled() is True
    assert app.tracing.get_tracer() is not None
