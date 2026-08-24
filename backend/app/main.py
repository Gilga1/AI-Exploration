"""FastAPI entrypoint for the Agentic RAG Evaluation Harness."""

from fastapi import FastAPI

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except ImportError:  # Allows the basic API shell to boot before extras are installed.
    trace = None

from app.core.config import get_settings

settings = get_settings()
_telemetry_configured = False


def configure_telemetry() -> None:
    """Configure asynchronous OTLP exporting only when an endpoint is supplied.

    Phase 0 must be runnable with no collector. Leaving the SDK's default provider
    in place makes tracing a no-op until OTEL_EXPORTER_OTLP_ENDPOINT is configured.
    """

    global _telemetry_configured

    if (
        trace is None
        or _telemetry_configured
        or not settings.otel_exporter_otlp_endpoint
    ):
        return

    try:
        resource = Resource.create(
            {
                "service.name": settings.otel_service_name,
                "deployment.environment": settings.environment,
            }
        )
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _telemetry_configured = True
    except Exception:
        # Telemetry is intentionally non-fatal during scaffolding. A later phase
        # will add structured logging and explicit observability failure handling.
        return


configure_telemetry()

app = FastAPI(title=settings.app_name)


@app.get("/health")
async def health() -> dict[str, str]:
    """Return a lightweight process health signal."""

    return {"status": "ok"}
