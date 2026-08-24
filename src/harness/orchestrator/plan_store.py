from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class PlanRecord:
    plan_id: str
    trace_id: str
    thread_id: str
    status: str
    message: str
    plan: dict[str, Any]
    task_results: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class PlanStore:
    """Persistent snapshots of plan runs for admin introspection."""

    def __init__(self, db_path: str = "data/harness_plans.db") -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plan_runs (
                plan_id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL DEFAULT '',
                plan_json TEXT NOT NULL,
                task_results_json TEXT NOT NULL DEFAULT '{}',
                metrics_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_trace ON plan_runs(trace_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_status ON plan_runs(status)")
        self._conn.commit()

    def upsert(self, record: PlanRecord) -> None:
        now = datetime.now(UTC).isoformat()
        created = record.created_at.isoformat()
        self._conn.execute(
            """
            INSERT INTO plan_runs
            (plan_id, trace_id, thread_id, status, message, plan_json, task_results_json, metrics_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(plan_id) DO UPDATE SET
                status = excluded.status,
                message = excluded.message,
                plan_json = excluded.plan_json,
                task_results_json = excluded.task_results_json,
                metrics_json = excluded.metrics_json,
                updated_at = excluded.updated_at
            """,
            (
                record.plan_id,
                record.trace_id,
                record.thread_id,
                record.status,
                record.message,
                json.dumps(record.plan, default=str),
                json.dumps(record.task_results, default=str),
                json.dumps(record.metrics, default=str),
                created,
                now,
            ),
        )
        self._conn.commit()

    def get(self, plan_id: str) -> PlanRecord | None:
        row = self._conn.execute("SELECT * FROM plan_runs WHERE plan_id = ?", (plan_id,)).fetchone()
        if row is None:
            return None
        return _row_to_record(row)

    def get_by_trace(self, trace_id: str) -> PlanRecord | None:
        row = self._conn.execute(
            "SELECT * FROM plan_runs WHERE trace_id = ? ORDER BY updated_at DESC LIMIT 1",
            (trace_id,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_record(row)

    def list_recent(self, *, limit: int = 50, status: str | None = None) -> list[PlanRecord]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM plan_runs WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM plan_runs ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_record(row) for row in rows]

    def metrics_summary(self) -> dict[str, Any]:
        total = self._conn.execute("SELECT COUNT(*) AS n FROM plan_runs").fetchone()["n"]
        by_status = self._conn.execute(
            "SELECT status, COUNT(*) AS n FROM plan_runs GROUP BY status"
        ).fetchall()
        success = self._conn.execute(
            "SELECT COUNT(*) AS n FROM plan_runs WHERE status IN ('completed', 'partial')"
        ).fetchone()["n"]
        return {
            "total_plans": total,
            "success_rate": (success / total) if total else 0.0,
            "by_status": {row["status"]: row["n"] for row in by_status},
        }


def _row_to_record(row: sqlite3.Row) -> PlanRecord:
    return PlanRecord(
        plan_id=row["plan_id"],
        trace_id=row["trace_id"],
        thread_id=row["thread_id"],
        status=row["status"],
        message=row["message"],
        plan=json.loads(row["plan_json"]),
        task_results=json.loads(row["task_results_json"]),
        metrics=json.loads(row["metrics_json"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )
