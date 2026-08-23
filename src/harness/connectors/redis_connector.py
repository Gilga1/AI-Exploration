from __future__ import annotations

import asyncio

from harness.config.models import ConnectorConfig
from harness.core.models import QueryResult, QuerySpec


class RedisConnector:
    def __init__(self, config: ConnectorConfig) -> None:
        self._config = config
        self._client = None

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def kind(self) -> str:
        return "redis"

    async def connect(self) -> None:
        import redis.asyncio as redis

        self._client = redis.Redis(
            host=self._config.host or "localhost",
            port=int(self._config.extra.get("port", 6379)),
            db=int(self._config.database or 0),
            password=self._config.password or None,
            ssl=self._config.extra.get("ssl", False),
            decode_responses=True,
        )

    async def health_check(self) -> bool:
        if self._client is None:
            await self.connect()
        assert self._client is not None
        return bool(await self._client.ping())

    async def query(self, spec: QuerySpec) -> QueryResult:
        if self._client is None:
            await self.connect()
        assert self._client is not None
        key = spec.filters.get("key") or spec.sql
        if not key:
            return QueryResult(rows=[])
        value = await self._client.get(key)
        return QueryResult(rows=[{"key": key, "value": value}])

    def as_retriever(self) -> object | None:
        return None
