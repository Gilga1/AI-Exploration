from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Span, Status, StatusCode


class OtelTracer:
    """OTel tracer using GenAI semantic conventions."""

    def __init__(self, service_name: str = "agent-harness") -> None:
        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        self._exporter = InMemorySpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(self._exporter))
        trace.set_tracer_provider(provider)
        self._tracer = trace.get_tracer("harness")

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

    def root_agent_span(
        self,
        *,
        trace_id: str,
        request_id: str,
    ) -> Iterator[Span]:
        return self.span(
            "invoke_agent",
            trace_id=trace_id,
            attributes={
                "gen_ai.operation.name": "invoke_agent",
                "harness.request_id": request_id,
            },
        )

    def routing_span(self, *, trace_id: str) -> Iterator[Span]:
        return self.span(
            "harness.routing",
            trace_id=trace_id,
            attributes={"harness.operation": "routing"},
        )

    def agent_span(self, *, trace_id: str, agent_id: str, agent_name: str) -> Iterator[Span]:
        return self.span(
            "invoke_agent",
            trace_id=trace_id,
            attributes={
                "gen_ai.operation.name": "invoke_agent",
                "gen_ai.agent.id": agent_id,
                "gen_ai.agent.name": agent_name,
            },
        )

    def tool_span(self, *, trace_id: str, tool_name: str) -> Iterator[Span]:
        return self.span(
            "execute_tool",
            trace_id=trace_id,
            attributes={
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": tool_name,
            },
        )

    def memory_span(
        self,
        *,
        trace_id: str,
        tier: str,
        operation: str,
        namespace: tuple[str, ...],
    ) -> Iterator[Span]:
        return self.span(
            "harness.memory.op",
            trace_id=trace_id,
            attributes={
                "harness.memory.tier": tier,
                "harness.memory.operation": operation,
                "harness.memory.namespace": ".".join(namespace),
            },
        )

    def handoff_span(self, *, trace_id: str, child_task_id: str) -> Iterator[Span]:
        return self.span(
            "harness.handoff",
            trace_id=trace_id,
            attributes={
                "harness.handoff.child_task_id": child_task_id,
            },
        )
