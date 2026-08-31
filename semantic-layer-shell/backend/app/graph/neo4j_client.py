from __future__ import annotations

import logging
from typing import Any

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

_neo4j_singleton: "Neo4jClient | None" = None


class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str) -> None:
        from neo4j import Driver, GraphDatabase

        self._GraphDatabase = GraphDatabase
        self._driver: Driver | None = None
        self._uri = uri
        self._user = user
        self._password = password
        self._connected = False
        self._last_error: str | None = None

    def connect(self) -> bool:
        try:
            if self._driver:
                self._driver.close()
            self._driver = self._GraphDatabase.driver(self._uri, auth=(self._user, self._password))
            self._driver.verify_connectivity()
            self._connected = True
            self._last_error = None
            return True
        except Exception as exc:
            self._connected = False
            self._driver = None
            self._last_error = str(exc)
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            self._driver = None
        self._connected = False

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if not self._driver:
            if not self.connect():
                return []
        assert self._driver is not None
        with self._driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def run_transaction(self, statements: list[tuple[str, dict[str, Any]]]) -> None:
        if not self._driver:
            if not self.connect():
                raise ConnectionError(
                    self._last_error or "Neo4j is not reachable — start with: docker compose up -d neo4j"
                )
        assert self._driver is not None

        def _tx(tx: Any) -> None:
            for query, params in statements:
                tx.run(query, params)

        with self._driver.session() as session:
            session.execute_write(_tx)


def get_neo4j_client() -> Neo4jClient:
    global _neo4j_singleton
    if _neo4j_singleton is None:
        settings = get_settings()
        _neo4j_singleton = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    return _neo4j_singleton
