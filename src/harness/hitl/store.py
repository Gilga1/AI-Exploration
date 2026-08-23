from __future__ import annotations

import sqlite3
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class PendingApproval:
    thread_id: str
    task_id: str
    agent_name: str
    trace_id: str
    interrupt_payload: dict[str, Any]
    created_at: datetime


class ApprovalStore:
    """Persistent store for HITL interrupts awaiting human decision."""

    def __init__(self, db_path: str = "data/harness_approvals.db") -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_approvals (
                task_id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                resolved_at TEXT
            )
            """
        )
        self._conn.commit()

    def save(self, approval: PendingApproval) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO pending_approvals
            (task_id, thread_id, agent_name, trace_id, payload, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                approval.task_id,
                approval.thread_id,
                approval.agent_name,
                approval.trace_id,
                json.dumps(approval.interrupt_payload, default=str),
                approval.created_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get(self, task_id: str) -> PendingApproval | None:
        row = self._conn.execute(
            "SELECT * FROM pending_approvals WHERE task_id = ? AND status = 'pending'",
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        return PendingApproval(
            thread_id=row["thread_id"],
            task_id=row["task_id"],
            agent_name=row["agent_name"],
            trace_id=row["trace_id"],
            interrupt_payload=json.loads(row["payload"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def resolve(self, task_id: str) -> None:
        self._conn.execute(
            "UPDATE pending_approvals SET status = 'resolved', resolved_at = ? WHERE task_id = ?",
            (datetime.now(UTC).isoformat(), task_id),
        )
        self._conn.commit()

    def list_pending(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT task_id, thread_id, agent_name, trace_id, payload, created_at "
            "FROM pending_approvals WHERE status = 'pending' ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "task_id": row["task_id"],
                "thread_id": row["thread_id"],
                "agent_name": row["agent_name"],
                "trace_id": row["trace_id"],
                "interrupt": json.loads(row["payload"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
