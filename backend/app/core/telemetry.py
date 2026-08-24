"""OpenTelemetry SDK configuration for the application.

The service must remain useful without an OTel Collector.  In that case an SDK
provider is still installed so instrumentation can create correctly-parented
spans, while the callback bridge stores completed spans locally instead of
attempting to send them over the network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.core.config import Settings

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
except ImportError:  # pragma: no cover - permits the minimal API shell to boot
    trace = None  # type: ignore[assignment]


@dataclass(frozen=True)
class TelemetryState:
    """Result of telemetry setup, used by the local persistence fallback."""

    configured: bool
    uses_otlp_exporter: bool
    exporter: str


_telemetry_state = TelemetryState(False, False, "unavailable")
_telemetry_configured = False


def configure_telemetry(settings: Settings) -> TelemetryState:
    """Install an SDK provider and optional asynchronous exporter.

    An OTLP endpoint enables ``BatchSpanProcessor`` + gRPC ``OTLPSpanExporter``.
    Without an endpoint the provider has no exporter (or a batch console
    exporter when explicitly requested), avoiding failed network calls while
    retaining trace context for the local span consumer.
    """

    global _telemetry_configured, _telemetry_state

    if _telemetry_configured:
        return _telemetry_state
    if trace is None:
        _telemetry_state = TelemetryState(False, False, "unavailable")
        return _telemetry_state

    try:
        resource_attributes: dict[str, Any] = {
            "service.name": settings.otel_service_name,
            "service.version": "0.1.0",
            "deployment.environment.name": settings.environment,
        }
        provider = TracerProvider(resource=Resource.create(resource_attributes))

        if settings.otel_exporter_otlp_endpoint:
            exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            exporter_name = "otlp"
            uses_otlp_exporter = True
        elif settings.otel_console_exporter:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            exporter_name = "console"
            uses_otlp_exporter = False
        else:
            # No processor is intentional: this is the no-op exporter mode.
            exporter_name = "noop"
            uses_otlp_exporter = False

        trace.set_tracer_provider(provider)
        _telemetry_configured = True
        _telemetry_state = TelemetryState(True, uses_otlp_exporter, exporter_name)
    except Exception:
        # Observability must never prevent the API from serving an offline RAG
        # request.  The callback bridge will still use its local no-op spans.
        _telemetry_state = TelemetryState(False, False, "unavailable")

    return _telemetry_state


def telemetry_uses_otlp_exporter() -> bool:
    """Return whether a collector is receiving spans from this process."""

    return _telemetry_state.uses_otlp_exporter


def get_tracer(name: str):
    """Return an OTel tracer when installed, otherwise ``None``."""

    return trace.get_tracer(name) if trace is not None else None
