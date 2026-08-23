from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.checkpoint.memory import MemorySaver

from harness.core.models import MemoryItem

if TYPE_CHECKING:
    from harness.config.connectors import YamlBackedConnector


class MemoryManager:
    """Facade over memory tiers. Phase 3 implements working memory only."""

    def __init__(
        self,
        checkpointer: MemorySaver | None = None,
        reflective_conn: YamlBackedConnector | None = None,
    ) -> None:
        self.working = checkpointer or MemorySaver()
        self.episodic = None
        self.reflective = reflective_conn

    async def recall(self, namespace: tuple[str, ...], query: str, k: int = 5) -> list[MemoryItem]:
        return []

    async def remember(self, namespace: tuple[str, ...], item: MemoryItem) -> None:
        return None
