from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config.settings import get_settings


class AuditStore:
    def __init__(self, db_path: str | None = None) -> None:
        settings = get_settings()
        self.db_path = db_path or settings.audit_db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    user_id TEXT,
                    question TEXT,
                    metric_id TEXT,
                    graph_version_id TEXT,
                    sql_hash TEXT,
                    sql_text TEXT,
                    row_count INTEGER,
                    node_ids TEXT,
                    edge_ids TEXT,
                    selection_confidence REAL,
                    extra TEXT
                )
                """
            )

    def log_query(
        self,
        *,
        user_id: str | None,
        question: str,
        metric_id: str | None,
        graph_version_id: str | None,
        sql_hash: str | None,
        sql_text: str | None,
        row_count: int,
        node_ids: list[str] | None = None,
        edge_ids: list[str] | None = None,
        selection_confidence: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO query_audit (
                    created_at, user_id, question, metric_id, graph_version_id,
                    sql_hash, sql_text, row_count, node_ids, edge_ids,
                    selection_confidence, extra
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(UTC).isoformat(),
                    user_id,
                    question,
                    metric_id,
                    graph_version_id,
                    sql_hash,
                    sql_text,
                    row_count,
                    json.dumps(node_ids or []),
                    json.dumps(edge_ids or []),
                    selection_confidence,
                    json.dumps(extra or {}),
                ),
            )
            return int(cursor.lastrowid)

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM query_audit ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
