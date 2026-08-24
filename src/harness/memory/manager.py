from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.checkpoint.memory import MemorySaver

from harness.core.models import MemoryItem
from harness.memory.episodic import EpisodicStore

if TYPE_CHECKING:
    from harness.config.connectors import YamlBackedConnector


class MemoryManager:
    """Facade over memory tiers: working (checkpointer), episodic (SQLite), reflective."""

    def __init__(
        self,
        checkpointer: MemorySaver | None = None,
        reflective_conn: YamlBackedConnector | None = None,
        episodic_db_path: str = "data/harness_episodic.db",
    ) -> None:
        self.working = checkpointer or MemorySaver()
        self.episodic = EpisodicStore(episodic_db_path)
        self.reflective = reflective_conn

    async def recall(self, namespace: tuple[str, ...], query: str, k: int = 5) -> list[MemoryItem]:
        return self.episodic.recall(namespace, query, k=k)

    async def remember(self, namespace: tuple[str, ...], item: MemoryItem) -> None:
        self.episodic.remember(namespace, item)
