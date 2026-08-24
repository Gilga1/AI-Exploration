from __future__ import annotations

from harness.core.errors import RegistryCollisionError
from harness.core.models import CapabilitySummary, QueryResult, QuerySpec
from harness.core.protocols import BaseDataConnector


class DataSourceRegistry:
    """Storage plane: postgres, warehouse, cache, vector connectors."""

    def __init__(self) -> None:
        self._connectors: dict[str, BaseDataConnector] = {}

    @property
    def connectors(self) -> dict[str, BaseDataConnector]:
        return dict(self._connectors)

    def register_connector(self, connector: BaseDataConnector) -> None:
        if connector.name in self._connectors:
            raise RegistryCollisionError(connector.name)
        self._connectors[connector.name] = connector

    def list_summaries(self) -> list[CapabilitySummary]:
        return [
            CapabilitySummary(
                kind="connector",
                name=connector.name,
                description=f"{connector.kind} data connector",
                metadata={"kind": connector.kind},
            )
            for connector in self._connectors.values()
        ]

    async def health_check_all(self, *, fail_fast: bool = False) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for name, connector in self._connectors.items():
            healthy = await connector.health_check()
            results[name] = healthy
            if fail_fast and not healthy:
                raise RuntimeError(f"Connector health check failed: {name}")
        return results
