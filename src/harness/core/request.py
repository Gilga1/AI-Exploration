from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class OrchestrationOptions(BaseModel):
    mode: Literal["auto", "single", "multi"] = "auto"


class IncomingRequest(BaseModel):
    message: str
    thread_id: str | None = None
    org_id: str = "default"
    user_id: str = "default"
    skill_input: dict[str, Any] | None = Field(
        default=None,
        description="Optional structured payload override for the routed skill",
    )
    tool_approvals: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Pre-approved tool decisions keyed by tool name, e.g. {'render_pdf_from_html': {'type': 'approve'}}",
    )
    orchestration: OrchestrationOptions = Field(default_factory=OrchestrationOptions)


class ResumeRequest(BaseModel):
    task_id: str
    thread_id: str
    decisions: list[dict[str, Any]] = Field(
        description="HITL decisions, e.g. [{'type': 'approve'}] or [{'type': 'reject', 'message': '...'}]"
    )


class OrchestratorResult(BaseModel):
    trace_id: str
    thread_id: str
    status: str
    message: str
    route: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] | None = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    task_id: str | None = None
    interrupts: list[dict[str, Any]] = Field(default_factory=list)
    plan: dict[str, Any] | None = None
    task_results: dict[str, Any] | None = None
