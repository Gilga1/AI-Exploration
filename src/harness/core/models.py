from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ExecutionMode(str, Enum):
    IN_PROCESS = "in_process"
    SUBPROCESS = "subprocess"
    SANDBOX = "sandbox"


class ToolSpec(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    capability_tags: list[str] = Field(default_factory=list)
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    side_effects: bool = False
    requires_approval: bool = False
    execution_mode: ExecutionMode = ExecutionMode.IN_PROCESS
    cost_estimate_usd: float | None = None
    timeout_s: int = 30


class SkillManifest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    capability_tags: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    system_prompt_fragment: str = ""
    sandboxed: bool = False


class AgentManifest(BaseModel):
    name: str
    description: str
    capability_tags: list[str] = Field(default_factory=list)
    system_prompt: str
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_skills: list[str] = Field(default_factory=list)
    context_packs: list[str] = Field(default_factory=list)
    model_config_ref: str = "primary_reasoner"
    max_steps: int = 25
    max_tokens_budget: int = 60_000
    timeout_s: int = 120
    interrupt_tools: list[str] = Field(
        default_factory=list,
        description="Tool names requiring human approval when invoked by this agent",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Agent-specific configuration (connectors, defaults, stub behavior, output formats)",
    )
    profile_of: str | None = Field(
        default=None,
        description="Base agent name when this manifest is a runtime profile instance",
    )


class ExecutionBudget(BaseModel):
    max_steps: int
    max_tokens: int
    timeout_s: int
    cost_ceiling_usd: float | None = None


class HandoffPacket(BaseModel):
    task_id: str
    parent_trace_id: str
    objective: str
    constraints: list[str] = Field(default_factory=list)
    context_summary: str
    budget: ExecutionBudget
    memory_namespace: tuple[str, ...]


class MemoryItem(BaseModel):
    id: str
    namespace: tuple[str, ...]
    content: str
    embedding: list[float] | None = None
    source_trace_id: str
    created_at: datetime
    salience_score: float = 1.0
    tags: list[str] = Field(default_factory=list)


class ArtifactRef(BaseModel):
    url: str
    kind: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    task_id: str
    status: Literal["success", "failure", "needs_clarification", "budget_exceeded", "awaiting_approval"]
    output: dict[str, Any] | None = None
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    proposed_memory_writes: list[MemoryItem] = Field(default_factory=list)
    trace_summary: str = ""


class QuerySpec(BaseModel):
    sql: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = 100


class QueryResult(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)


class CapabilitySummary(BaseModel):
    kind: Literal["tool", "skill", "agent", "connector"]
    name: str
    description: str
    capability_tags: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
