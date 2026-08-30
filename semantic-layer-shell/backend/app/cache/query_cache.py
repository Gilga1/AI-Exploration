from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.config.settings import get_settings


class QueryResultCache:
    """Cache keyed by resolved graph identity — not natural-language question text."""

    def __init__(self, db_path: str | None = None) -> None:
        settings = get_settings()
        self.db_path = db_path or settings.query_cache_db_path
        self.ttl_seconds = settings.query_cache_ttl_seconds
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @staticmethod
    def make_key(
        *,
        graph_version_id: str | None,
        node_ids: list[str],
        edge_ids: list[str],
        parameters: dict[str, str] | None,
        dimensions: list[str] | None,
        sql_hash: str,
    ) -> str:
        payload = {
            "graph_version_id": graph_version_id,
            "node_ids": sorted(node_ids),
            "edge_ids": sorted(edge_ids),
            "parameters": parameters or {},
            "dimensions": sorted(dimensions or []),
            "sql_hash": sql_hash,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_cache (
                    cache_key TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    rows_json TEXT NOT NULL,
                    columns_json TEXT NOT NULL,
                    row_count INTEGER NOT NULL
                )
                """
            )

    def get(self, cache_key: str) -> tuple[list[dict[str, Any]], list[str]] | None:
        now = datetime.now(UTC).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT rows_json, columns_json FROM query_cache WHERE cache_key = ? AND expires_at > ?",
                (cache_key, now),
            ).fetchone()
            if not row:
                return None
            return json.loads(row[0]), json.loads(row[1])

    def set(
        self,
        cache_key: str,
        rows: list[dict[str, Any]],
        columns: list[str],
    ) -> None:
        created = datetime.now(UTC)
        expires = created + timedelta(seconds=self.ttl_seconds)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO query_cache
                (cache_key, created_at, expires_at, rows_json, columns_json, row_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    cache_key,
                    created.isoformat(),
                    expires.isoformat(),
                    json.dumps(rows, default=str),
                    json.dumps(columns),
                    len(rows),
                ),
            )
