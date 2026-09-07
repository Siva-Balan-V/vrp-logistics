from __future__ import annotations

import structlog

_logger = structlog.get_logger(__name__)

_TRACER = None
_tracing_enabled = False


def is_tracing_enabled() -> bool:
    """True once ``setup_tracing`` has been called with a valid OTLP endpoint."""
    return _tracing_enabled


def setup_tracing(otlp_endpoint: str | None, service_name: str) -> None:
    """Initialize OpenTelemetry when an OTLP endpoint is configured.

    This is a no-op when ``otlp_endpoint`` is falsy, so tracing stays fully
    disabled unless explicitly configured.
    """
    global _TRACER, _tracing_enabled

    if not otlp_endpoint or _tracing_enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
        trace.set_tracer_provider(provider)
        _TRACER = trace.get_tracer(service_name)
        _tracing_enabled = True
        _logger.info("tracing_initialized", endpoint=otlp_endpoint)
    except Exception as exc:  # pragma: no cover - defensive, depends on optional deps
        _logger.warning("tracing_init_failed", error=str(exc))


def get_tracer():
    """Return the module-level tracer, or ``None`` if tracing is not initialized."""
    return _TRACER
