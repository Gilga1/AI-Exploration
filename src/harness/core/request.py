from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IncomingRequest(BaseModel):
    message: str
    thread_id: str | None = None
    org_id: str = "default"
    user_id: str = "default"
    skill_input: dict[str, Any] | None = Field(
        default=None,
        description="Optional structured payload override for the routed skill",
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
