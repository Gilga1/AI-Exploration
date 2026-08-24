from __future__ import annotations

import asyncio

from harness.config.models import ConnectorConfig
from harness.core.models import QueryResult, QuerySpec


class SnowflakeConnector:
    """Snowflake warehouse connector."""

    def __init__(self, config: ConnectorConfig) -> None:
        self._config = config
        self._conn = None

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def kind(self) -> str:
        return "snowflake"

    def _connect_sync(self):
        try:
            import snowflake.connector
        except ImportError as exc:
            raise ImportError(
                "Snowflake connector requires snowflake-connector-python. "
                "Install with: pip install -r requirements-snowflake.txt"
            ) from exc

        return snowflake.connector.connect(
            account=self._config.extra.get("account"),
            user=self._config.user,
            password=self._config.password,
            warehouse=self._config.extra.get("warehouse"),
            database=self._config.database,
            schema=self._config.extra.get("schema", "PUBLIC"),
            role=self._config.extra.get("role"),
        )

    async def connect(self) -> None:
        self._conn = await asyncio.to_thread(self._connect_sync)

    async def health_check(self) -> bool:
        if self._conn is None:
            await self.connect()
        assert self._conn is not None

        def _check():
            cur = self._conn.cursor()
            cur.execute(self._config.health_check_query or "SELECT 1")
            cur.fetchone()
            cur.close()

        await asyncio.to_thread(_check)
        return True

    async def query(self, spec: QuerySpec) -> QueryResult:
        if self._conn is None:
            await self.connect()
        assert self._conn is not None
        if not spec.sql:
            return QueryResult(rows=[])

        def _run():
            cur = self._conn.cursor()
            cur.execute(spec.sql, spec.filters or None)
            columns = [col[0] for col in cur.description] if cur.description else []
            fetched = cur.fetchmany(spec.limit)
            cur.close()
            return [dict(zip(columns, row)) for row in fetched]

        rows = await asyncio.to_thread(_run)
        return QueryResult(rows=rows)

    def as_retriever(self) -> object | None:
        return None
