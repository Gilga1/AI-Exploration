from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from harness.core.models import MemoryItem


class EpisodicStore:
    """SQLite-backed episodic memory tier."""

    def __init__(self, db_path: str = "data/harness_episodic.db") -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_items (
                id TEXT PRIMARY KEY,
                namespace TEXT NOT NULL,
                content TEXT NOT NULL,
                source_trace_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                salience_score REAL NOT NULL DEFAULT 1.0,
                tags TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_namespace ON memory_items(namespace)")
        self._conn.commit()

    def remember(self, namespace: tuple[str, ...], item: MemoryItem) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO memory_items
            (id, namespace, content, source_trace_id, created_at, salience_score, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.id or uuid.uuid4().hex,
                ".".join(namespace),
                item.content,
                item.source_trace_id,
                item.created_at.isoformat(),
                item.salience_score,
                json.dumps(item.tags),
            ),
        )
        self._conn.commit()

    def recall(self, namespace: tuple[str, ...], query: str, k: int = 5) -> list[MemoryItem]:
        ns = ".".join(namespace)
        rows = self._conn.execute(
            """
            SELECT * FROM memory_items
            WHERE namespace = ? AND content LIKE ?
            ORDER BY salience_score DESC, created_at DESC
            LIMIT ?
            """,
            (ns, f"%{query}%", k),
        ).fetchall()
        return [
            MemoryItem(
                id=row["id"],
                namespace=tuple(row["namespace"].split(".")),
                content=row["content"],
                source_trace_id=row["source_trace_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                salience_score=row["salience_score"],
                tags=json.loads(row["tags"]),
            )
            for row in rows
        ]
