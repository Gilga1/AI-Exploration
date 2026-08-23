from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class TraceEventBase(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    latency_ms: int | None = None


class RoutingDecisionEvent(TraceEventBase):
    candidates: list[dict[str, Any]]
    selected: str
    selected_kind: str
    rationale: str
    confidence: float
    used_llm: bool = False


class ToolInvocationEvent(TraceEventBase):
    tool_name: str
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    rationale: str = ""
    error: str | None = None


class MemoryOperationEvent(TraceEventBase):
    tier: str
    operation: str
    namespace: tuple[str, ...]
