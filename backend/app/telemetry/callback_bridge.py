"""LangChain callback handler that mirrors execution into OpenTelemetry spans."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

from app.core.telemetry import get_tracer, telemetry_uses_otlp_exporter
from app.telemetry.semantic_conventions import (
    attribute_value,
    input_attributes,
    model_attributes,
    output_attributes,
    retrieval_attributes,
    usage_attributes,
)

try:
    from langchain_core.callbacks import BaseCallbackHandler
except ImportError:  # pragma: no cover - allows offline shell startup before LangChain is installed
    class BaseCallbackHandler:  # type: ignore[no-redef]
        """Minimal compatibility base; real deployments use LangChain's handler."""


try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
except ImportError:  # pragma: no cover - local persistence still works without SDK extras
    trace = None  # type: ignore[assignment]
    Status = StatusCode = None  # type: ignore[assignment,misc]


@dataclass
class _ActiveSpan:
    run_id: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    kind: str
    started_at: datetime
    started_counter: float
    span: Any | None
    attributes: dict[str, Any] = field(default_factory=dict)


class LangChainOTelCallbackHandler(BaseCallbackHandler):
    """Create one OTel span for each LangChain chain, LLM, retriever, or tool run.

    The bridge owns the only coupling between LangChain callback payloads and
    OTel.  It also sends completed spans to the SQLAlchemy store when no OTLP
    Collector endpoint is configured.
    """

    raise_error = False
    run_inline = True

    def __init__(self) -> None:
        super().__init__()
        self._tracer = get_tracer("app.telemetry.langchain")
        self._active: dict[str, _ActiveSpan] = {}
        self._lock = RLock()

    def new_run_id(self) -> UUID:
        """Mint a fresh run id for callers driving the handler manually."""

        return uuid4()

    def on_chain_start(
        self,
        serialized: dict[str, Any] | None,
        inputs: dict[str, Any] | Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **_: Any,
    ) -> None:
        self._open("chain", serialized, inputs, run_id, parent_run_id)

    def on_chain_end(self, outputs: dict[str, Any] | Any, *, run_id: UUID, **_: Any) -> None:
        self._close(run_id, output_attributes(outputs))

    def on_chain_error(self, error: BaseException, *, run_id: UUID, **_: Any) -> None:
        self._close(run_id, {"error.type": type(error).__name__, "error.message": str(error)}, error)

    def on_llm_start(
        self,
        serialized: dict[str, Any] | None,
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **_: Any,
    ) -> None:
        self._open("llm", serialized, prompts, run_id, parent_run_id)

    def on_chat_model_start(
        self,
        serialized: dict[str, Any] | None,
        messages: list[list[Any]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **_: Any,
    ) -> None:
        self._open("llm", serialized, messages, run_id, parent_run_id)

    def on_llm_end(self, response: Any, *, run_id: UUID, **_: Any) -> None:
        self._close(run_id, {**output_attributes(self._response_text(response)), **usage_attributes(response)})

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **_: Any) -> None:
        self._close(run_id, {"error.type": type(error).__name__, "error.message": str(error)}, error)

    def on_retriever_start(
        self,
        serialized: dict[str, Any] | None,
        query: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **_: Any,
    ) -> None:
        self._open("retriever", serialized, query, run_id, parent_run_id)

    def on_retriever_end(self, documents: list[Any], *, run_id: UUID, **_: Any) -> None:
        contents = [getattr(document, "page_content", str(document)) for document in documents]
        self._close(run_id, {**output_attributes(contents), **retrieval_attributes(documents)})

    def on_retriever_error(self, error: BaseException, *, run_id: UUID, **_: Any) -> None:
        self._close(run_id, {"error.type": type(error).__name__, "error.message": str(error)}, error)

    def on_tool_start(
        self,
        serialized: dict[str, Any] | None,
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **_: Any,
    ) -> None:
        self._open("tool", serialized, input_str, run_id, parent_run_id)

    def on_tool_end(self, output: Any, *, run_id: UUID, **_: Any) -> None:
        self._close(run_id, output_attributes(output))

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **_: Any) -> None:
        self._close(run_id, {"error.type": type(error).__name__, "error.message": str(error)}, error)

    def _open(
        self,
        kind: str,
        serialized: dict[str, Any] | None,
        input_value: Any,
        run_id: UUID,
        parent_run_id: UUID | None,
    ) -> None:
        run_key = str(run_id)
        parent_key = str(parent_run_id) if parent_run_id else None
        with self._lock:
            parent = self._active.get(parent_key) if parent_key else None
            serialized = serialized or {}
            operation_name = self._operation_name(kind, serialized)
            attributes = input_attributes(input_value)
            if kind == "llm":
                attributes.update(model_attributes(serialized))
            elif kind == "tool":
                attributes["gen_ai.tool.name"] = attribute_value(serialized.get("name", "tool"))

            span = self._start_otel_span(operation_name, parent)
            trace_id, span_id = self._span_identifiers(span, parent)
            active = _ActiveSpan(
                run_id=run_key,
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent.span_id if parent else None,
                name=operation_name,
                kind=kind,
                started_at=datetime.now(timezone.utc),
                started_counter=perf_counter(),
                span=span,
                attributes={},
            )
            self._set_attributes(active, attributes)
            self._active[run_key] = active

    def _close(
        self,
        run_id: UUID,
        attributes: dict[str, Any] | None = None,
        error: BaseException | None = None,
    ) -> None:
        with self._lock:
            active = self._active.pop(str(run_id), None)
        if active is None:
            return

        if attributes:
            self._set_attributes(active, attributes)
        ended_at = datetime.now(timezone.utc)
        duration_ms = round((perf_counter() - active.started_counter) * 1_000, 3)
        status = "ERROR" if error else "OK"
        if active.span is not None:
            try:
                if error is not None:
                    active.span.record_exception(error)
                    if Status is not None and StatusCode is not None:
                        active.span.set_status(Status(StatusCode.ERROR, str(error)))
                elif Status is not None and StatusCode is not None:
                    active.span.set_status(Status(StatusCode.OK))
                active.span.end()
            except Exception:
                # Export failures are intentionally isolated from the RAG request.
                pass

        if not telemetry_uses_otlp_exporter():
            try:
                from app.db.session import persist_completed_span

                persist_completed_span(
                    trace_id=active.trace_id,
                    span_id=active.span_id,
                    parent_span_id=active.parent_span_id,
                    name=active.name,
                    kind=active.kind,
                    start_time=active.started_at,
                    end_time=ended_at,
                    duration_ms=duration_ms,
                    status=status,
                    attributes=active.attributes,
                    is_root=active.parent_span_id is None,
                )
            except Exception:
                # Local persistence is a dev-mode observability aid and should
                # never change the chain's user-visible result.
                pass

    def _start_otel_span(self, name: str, parent: _ActiveSpan | None) -> Any | None:
        if self._tracer is None:
            return None
        try:
            if parent and parent.span is not None and trace is not None:
                parent_context = trace.set_span_in_context(parent.span)
                return self._tracer.start_span(name, context=parent_context)
            return self._tracer.start_span(name)
        except Exception:
            return None

    @staticmethod
    def _operation_name(kind: str, serialized: dict[str, Any]) -> str:
        raw_name = serialized.get("name") or serialized.get("id") or kind
        if isinstance(raw_name, (list, tuple)):
            raw_name = raw_name[-1] if raw_name else kind
        return f"{kind}.{raw_name}"

    @staticmethod
    def _response_text(response: Any) -> Any:
        if isinstance(response, str):
            return response
        generations = getattr(response, "generations", None)
        if generations and generations[0]:
            return getattr(generations[0][0], "text", str(generations[0][0]))
        return getattr(response, "content", response)

    @staticmethod
    def _span_identifiers(span: Any | None, parent: _ActiveSpan | None) -> tuple[str, str]:
        if span is not None:
            try:
                context = span.get_span_context()
                if context.is_valid:
                    return f"{context.trace_id:032x}", f"{context.span_id:016x}"
            except Exception:
                pass
        return (parent.trace_id if parent else uuid4().hex, uuid4().hex[:16])

    @staticmethod
    def _set_attributes(active: _ActiveSpan, attributes: dict[str, Any]) -> None:
        for key, value in attributes.items():
            normalized = attribute_value(value)
            active.attributes[key] = normalized
            if active.span is not None:
                try:
                    active.span.set_attribute(key, normalized)
                except Exception:
                    pass
