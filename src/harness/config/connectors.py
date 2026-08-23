from __future__ import annotations

from harness.config.models import ConnectorConfig
from harness.core.models import QueryResult, QuerySpec


class YamlBackedConnector:
    """Connector instantiated from YAML config plane (Phase 2)."""

    def __init__(self, config: ConnectorConfig) -> None:
        self._config = config
        self._connected = False

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def kind(self) -> str:
        return self._config.kind

    @property
    def config(self) -> ConnectorConfig:
        return self._config

    async def connect(self) -> None:
        self._connected = True

    async def health_check(self) -> bool:
        if self._config.health_check_query:
            return bool(self._config.host or self._config.kind == "redis")
        return True

    async def query(self, spec: QuerySpec) -> QueryResult:
        return QueryResult(rows=[])

    def as_retriever(self) -> object | None:
        if self._config.kind == "vector_index":
            return {"connector": self.name, "kind": "vector_index"}
        return None
