from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from harness.core.models import ExecutionBudget


class TraceEventBase(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    latency_ms: int | None = None
    event_type: str = ""


class RoutingDecisionEvent(TraceEventBase):
    event_type: str = "routing"
    candidates: list[dict[str, Any]]
    selected: str
    selected_kind: str
    rationale: str
    confidence: float
    used_llm: bool = False


class ToolInvocationEvent(TraceEventBase):
    event_type: str = "tool"
    tool_name: str
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    rationale: str = ""
    error: str | None = None
    capture_content: bool = False


class AgentThoughtEvent(TraceEventBase):
    event_type: str = "agent_thought"
    agent_name: str
    thought: str
    capture_content: bool = True


class MemoryOperationEvent(TraceEventBase):
    event_type: str = "memory"
    tier: Literal["working", "episodic", "reflective"]
    operation: Literal["read", "write"]
    namespace: tuple[str, ...]


class HandoffEvent(TraceEventBase):
    event_type: str = "handoff"
    child_task_id: str
    agent_name: str
    budget: ExecutionBudget
    status: str


class LLMCallEvent(TraceEventBase):
    event_type: str = "llm"
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = ""
    cost_usd: float | None = None
    capture_content: bool = False
    prompt_preview: str | None = None
    completion_preview: str | None = None
