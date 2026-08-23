from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Iterator


class EventLedger:
    """In-memory SQLite ledger for waterfall UI and audit queries."""

    def __init__(self) -> None:
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                span_id TEXT NOT NULL,
                parent_span_id TEXT,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                latency_ms INTEGER,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.execute("CREATE INDEX idx_events_trace ON events(trace_id)")
        self._conn.execute("CREATE INDEX idx_events_span ON events(span_id)")
        self._conn.commit()

    def write(self, event: dict[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO events (trace_id, span_id, parent_span_id, event_type, timestamp, latency_ms, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.get("trace_id"),
                event.get("span_id"),
                event.get("parent_span_id"),
                event.get("event_type", "unknown"),
                event.get("timestamp", datetime.now(UTC).isoformat()),
                event.get("latency_ms"),
                json.dumps(event, default=str),
            ),
        )
        self._conn.commit()

    def list_by_trace(self, trace_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT payload FROM events WHERE trace_id = ? ORDER BY id",
            (trace_id,),
        ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def list_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT payload FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [json.loads(row["payload"]) for row in reversed(rows)]

    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            yield
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def close(self) -> None:
        self._conn.close()
