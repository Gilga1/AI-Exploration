from __future__ import annotations

from typing import Any

from harness.config.models import ConnectorConfig
from harness.core.models import QueryResult, QuerySpec


class PostgresConnector:
    """Async Postgres connector (Azure Database for PostgreSQL compatible)."""

    def __init__(self, config: ConnectorConfig) -> None:
        self._config = config
        self._pool = None

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def kind(self) -> str:
        return "postgres"

    async def connect(self) -> None:
        import asyncpg

        ssl_mode = self._config.extra.get("ssl_mode", "prefer")
        self._pool = await asyncpg.create_pool(
            host=self._config.host,
            port=int(self._config.extra.get("port", 5432)),
            database=self._config.database,
            user=self._config.user,
            password=self._config.password,
            min_size=1,
            max_size=self._config.pool_size,
            ssl="require" if ssl_mode == "require" else None,
        )

    async def health_check(self) -> bool:
        if self._pool is None:
            await self.connect()
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            query = self._config.health_check_query or "SELECT 1"
            await conn.fetchval(query)
        return True

    async def query(self, spec: QuerySpec) -> QueryResult:
        if self._pool is None:
            await self.connect()
        assert self._pool is not None
        if not spec.sql:
            return QueryResult(rows=[])

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(spec.sql, *list(spec.filters.values()))
        return QueryResult(rows=[dict(row) for row in rows[: spec.limit]])

    def as_retriever(self) -> object | None:
        return None

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
