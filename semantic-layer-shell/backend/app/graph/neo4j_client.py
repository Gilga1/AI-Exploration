from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase, Driver

from app.config.settings import get_settings


class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str) -> None:
        self._driver: Driver | None = None
        self._uri = uri
        self._user = user
        self._password = password
        self._connected = False

    def connect(self) -> bool:
        try:
            self._driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))
            self._driver.verify_connectivity()
            self._connected = True
            return True
        except Exception:
            self._connected = False
            self._driver = None
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected

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
                # Offline mode: no-op for local dev without Neo4j
                return
        assert self._driver is not None

        def _tx(tx: Any) -> None:
            for query, params in statements:
                tx.run(query, params)

        with self._driver.session() as session:
            session.execute_write(_tx)


def get_neo4j_client() -> Neo4jClient:
    settings = get_settings()
    return Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
