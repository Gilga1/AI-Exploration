from __future__ import annotations

import random
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

from harness.telemetry.events import TraceEventBase
from harness.telemetry.ledger import EventLedger
from harness.telemetry.otel import OtelTracer

_current_parent_span: ContextVar[str | None] = ContextVar("parent_span_id", default=None)


class TelemetryBus:
    def __init__(
        self,
        *,
        content_sample_rate: float = 0.0,
        enable_otel: bool = True,
        enable_ledger: bool = True,
        ledger_db_path: str = "data/harness_events.db",
        langfuse_enabled: bool = True,
    ) -> None:
        self._events: list[TraceEventBase] = []
        self._content_sample_rate = content_sample_rate
        langfuse = None
        if enable_otel and langfuse_enabled:
            from harness.telemetry.otel import resolve_langfuse_config

            langfuse = resolve_langfuse_config()
        self._otel = OtelTracer(langfuse=langfuse) if enable_otel else None
        self._ledger = EventLedger(ledger_db_path) if enable_ledger else None

    @property
    def ledger(self) -> EventLedger | None:
        return self._ledger

    def new_span_id(self) -> str:
        return uuid.uuid4().hex[:16]

    def should_capture_content(self) -> bool:
        if self._content_sample_rate <= 0:
            return False
        if self._content_sample_rate >= 1:
            return True
        return random.random() < self._content_sample_rate

    def emit(self, event: TraceEventBase) -> None:
        parent = _current_parent_span.get()
        if parent and event.parent_span_id is None:
            event.parent_span_id = parent
        self._events.append(event)
        payload = event.model_dump(mode="json")
        if self._ledger is not None:
            self._ledger.write(payload)

    def list_events(self) -> list[dict[str, Any]]:
        return [event.model_dump(mode="json") for event in self._events]

    def list_events_for_trace(self, trace_id: str) -> list[dict[str, Any]]:
        if self._ledger is not None:
            return self._ledger.list_by_trace(trace_id)
        return [e for e in self.list_events() if e.get("trace_id") == trace_id]

    @contextmanager
    def span(
        self,
        name: str,
        *,
        trace_id: str,
        span_id: str | None = None,
        otel_attributes: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        sid = span_id or self.new_span_id()
        token = _current_parent_span.set(sid)
        start = time.perf_counter()
        otel_ctx = None
        if self._otel is not None:
            otel_ctx = self._otel.span(name, trace_id=trace_id, attributes=otel_attributes)
            otel_ctx.__enter__()
        try:
            yield sid
        finally:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            _current_parent_span.reset(token)
            if otel_ctx is not None:
                otel_ctx.__exit__(None, None, None)

    def export_otel_spans(self) -> list[dict[str, Any]]:
        if self._otel is None:
            return []
        return self._otel.export_spans()

    def flush_otel(self) -> None:
        if self._otel is not None:
            self._otel.flush()

    @property
    def langfuse_enabled(self) -> bool:
        return self._otel is not None and self._otel.langfuse_enabled

    def clear(self) -> None:
        self._events.clear()
