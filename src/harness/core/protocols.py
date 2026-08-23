from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

from pydantic import BaseModel

from harness.core.models import (
    AgentManifest,
    AgentResult,
    HandoffPacket,
    QueryResult,
    QuerySpec,
    SkillManifest,
    ToolSpec,
)

if TYPE_CHECKING:
    from harness.core.context import RunContext
    from harness.registry.registry import ToolRegistry


@runtime_checkable
class BaseTool(Protocol):
    spec: ToolSpec

    async def run(self, args: BaseModel, *, context: RunContext) -> BaseModel: ...


class BaseSkill(ABC):
    manifest: SkillManifest

    @abstractmethod
    async def execute(self, payload: BaseModel, *, context: RunContext) -> BaseModel: ...

    def validate_input(self, raw: dict) -> BaseModel:
        return self.manifest.input_schema.model_validate(raw)


class BaseAgent(ABC):
    manifest: AgentManifest

    @abstractmethod
    def compile(self, *, tool_registry: ToolRegistry, memory: object) -> object:
        """Return a LangGraph-compiled subgraph (Phase 7)."""

    @abstractmethod
    async def run(self, packet: HandoffPacket) -> AgentResult: ...


@runtime_checkable
class BaseDataConnector(Protocol):
    name: str
    kind: Literal["postgres", "snowflake", "redis", "vector_index"]

    async def connect(self) -> None: ...

    async def health_check(self) -> bool: ...

    async def query(self, spec: QuerySpec) -> QueryResult: ...

    def as_retriever(self) -> object | None: ...
