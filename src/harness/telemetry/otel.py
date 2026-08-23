from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Span, Status, StatusCode


@dataclass
class LangfuseConfig:
    public_key: str
    secret_key: str
    base_url: str = "https://cloud.langfuse.com"


def resolve_langfuse_config() -> LangfuseConfig | None:
    public_key = (
        os.environ.get("LANGFUSE_PUBLIC_KEY")
        or os.environ.get("HARNESS_SECRET_LANGFUSE_PUBLIC_KEY")
        or os.environ.get("HARNESS_LANGFUSE_PUBLIC_KEY")
    )
    secret_key = (
        os.environ.get("LANGFUSE_SECRET_KEY")
        or os.environ.get("HARNESS_SECRET_LANGFUSE_SECRET_KEY")
        or os.environ.get("HARNESS_LANGFUSE_SECRET_KEY")
    )
    if not public_key or not secret_key:
        return None
    base_url = (
        os.environ.get("LANGFUSE_BASE_URL")
        or os.environ.get("HARNESS_LANGFUSE_BASE_URL")
        or "https://cloud.langfuse.com"
    )
    return LangfuseConfig(public_key=public_key, secret_key=secret_key, base_url=base_url.rstrip("/"))


class OtelTracer:
    """OTel tracer using GenAI semantic conventions with optional Langfuse export."""

    def __init__(
        self,
        service_name: str = "agent-harness",
        *,
        langfuse: LangfuseConfig | None = None,
    ) -> None:
        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        self._exporter = InMemorySpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(self._exporter))

        self._langfuse_client = None
        if langfuse is not None:
            self._langfuse_client = self._setup_langfuse(provider, langfuse)

        trace.set_tracer_provider(provider)
        self._tracer = trace.get_tracer("harness")
        self._langfuse_config = langfuse

    def _setup_langfuse(self, provider: TracerProvider, config: LangfuseConfig) -> Any:
        from langfuse import Langfuse
        from langfuse._client.span_processor import LangfuseSpanProcessor

        provider.add_span_processor(
            LangfuseSpanProcessor(
                public_key=config.public_key,
                secret_key=config.secret_key,
                base_url=config.base_url,
            )
        )
        return Langfuse(
            public_key=config.public_key,
            secret_key=config.secret_key,
            base_url=config.base_url,
            tracer_provider=provider,
        )

    @property
    def langfuse_enabled(self) -> bool:
        return self._langfuse_config is not None

    def flush(self) -> None:
        if self._langfuse_client is not None:
            self._langfuse_client.flush()

    @contextmanager
    def span(
        self,
        name: str,
        *,
        trace_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[Span]:
        attrs = {"harness.trace_id": trace_id, **(attributes or {})}
        with self._tracer.start_as_current_span(name, attributes=attrs) as span:
            yield span

    def record_exception(self, span: Span, exc: BaseException) -> None:
        span.record_exception(exc)
        span.set_status(Status(StatusCode.ERROR, str(exc)))

    def export_spans(self) -> list[dict[str, Any]]:
        spans = self._exporter.get_finished_spans()
        self._exporter.clear()
        return [
            {
                "name": span.name,
                "trace_id": format(span.context.trace_id, "032x"),
                "span_id": format(span.context.span_id, "016x"),
                "attributes": dict(span.attributes or {}),
                "status": span.status.status_code.name,
            }
            for span in spans
        ]
