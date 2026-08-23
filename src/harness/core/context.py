from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from harness.core.protocols import BaseTool


@dataclass
class RunContext:
    """Execution context injected into tools and skills at runtime."""

    trace_id: str
    tools: dict[str, BaseTool] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    async def store_artifact(self, data: bytes, *, kind: str) -> dict[str, Any]:
        """Placeholder artifact store — replaced in a later phase."""
        return {
            "url": f"artifact://{kind}/{len(data)}-bytes",
            "kind": kind,
            "metadata": {"size": len(data)},
        }
