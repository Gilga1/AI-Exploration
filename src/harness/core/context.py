from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from harness.core.protocols import BaseTool
    from harness.memory.artifacts import ArtifactStore
    from harness.memory.manager import MemoryManager


@dataclass
class RunContext:
    """Execution context injected into tools and skills at runtime."""

    trace_id: str
    tools: dict[str, BaseTool] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    thread_id: str | None = None
    memory: MemoryManager | None = None
    artifacts: ArtifactStore | None = None

    async def store_artifact(self, data: bytes, *, kind: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.artifacts is not None:
            return await self.artifacts.store(data, kind=kind, metadata=metadata)
        return {
            "url": f"artifact://{kind}/{len(data)}-bytes",
            "kind": kind,
            "metadata": {"size": len(data), **(metadata or {})},
        }
