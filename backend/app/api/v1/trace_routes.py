"""Read-only API endpoints for locally persisted Phase 2 OTel traces."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.db.models import Span, Trace
from app.db.session import init_db, session_scope

router = APIRouter(prefix="/traces", tags=["traces"])


def _isoformat(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _trace_payload(trace_record: Trace) -> dict[str, Any]:
    return {
        "id": trace_record.id,
        "name": trace_record.name,
        "start_time": _isoformat(trace_record.start_time),
        "end_time": _isoformat(trace_record.end_time),
        "duration_ms": trace_record.duration_ms,
        "status": trace_record.status,
        "attributes": trace_record.attributes,
    }


def _span_payload(span_record: Span) -> dict[str, Any]:
    return {
        "id": span_record.id,
        "trace_id": span_record.trace_id,
        "parent_span_id": span_record.parent_span_id,
        "name": span_record.name,
        "kind": span_record.kind,
        "start_time": _isoformat(span_record.start_time),
        "end_time": _isoformat(span_record.end_time),
        "duration_ms": span_record.duration_ms,
        "status": span_record.status,
        "attributes": span_record.attributes,
    }


@router.get("")
def list_traces(limit: int = 50) -> list[dict[str, Any]]:
    """Return most recently started traces, capped to protect the dashboard."""

    init_db()
    clamped_limit = max(1, min(limit, 200))
    with session_scope() as session:
        traces = session.scalars(
            select(Trace).order_by(Trace.start_time.desc()).limit(clamped_limit)
        ).all()
        return [_trace_payload(trace_record) for trace_record in traces]


@router.get("/{trace_id}")
def get_trace(trace_id: str) -> dict[str, Any]:
    """Return a trace plus all of its completed spans in chronological order."""

    init_db()
    with session_scope() as session:
        trace_record = session.get(Trace, trace_id)
        if trace_record is None:
            raise HTTPException(status_code=404, detail="Trace not found")
        spans = session.scalars(
            select(Span).where(Span.trace_id == trace_id).order_by(Span.start_time.asc())
        ).all()
        return {**_trace_payload(trace_record), "spans": [_span_payload(span) for span in spans]}
