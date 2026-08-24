"""Aggregated and per-trace RAG metric reporting for the dashboard."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, select

from app.db.models import EvalResult, Trace
from app.db.session import session_scope
from app.evaluation.runners.realtime_worker import score_pending_traces

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/rag")
def rag_metrics(per_trace: bool = False) -> dict[str, Any]:
    """Aggregate RAG judge scores; optionally include per-trace breakdowns."""

    with session_scope() as session:
        # Opportunistic backstop: score anything the worker missed (respects sampling).
        try:
            score_pending_traces(limit=10)
        except Exception:  # Metrics endpoint must never fail because of the worker.
            pass

        rows = session.execute(
            select(
                EvalResult.metric_name,
                EvalResult.score,
                EvalResult.status,
                EvalResult.trace_id,
                EvalResult.reasoning,
                EvalResult.created_at,
            ).order_by(EvalResult.created_at.asc())
        ).all()

    by_metric: dict[str, list[float]] = defaultdict(list)
    per_trace_rows: list[dict[str, Any]] = []
    trace_names: dict[str, str] = {}

    for metric_name, score, status, trace_id, reasoning, created_at in rows:
        if score is not None:
            by_metric[metric_name].append(score)
        if per_trace:
            per_trace_rows.append(
                {
                    "trace_id": trace_id,
                    "metric": metric_name,
                    "score": score,
                    "status": status,
                    "reasoning": reasoning,
                    "scored_at": created_at.isoformat() if created_at else None,
                }
            )

    summary = []
    for name in ("Faithfulness", "ContextualPrecision", "ContextualRecall", "Hallucination"):
        scores = by_metric.get(name, [])
        scored = [s for s in scores if s is not None]
        summary.append(
            {
                "name": name,
                "avg_score": round(sum(scored) / len(scored), 4) if scored else None,
                "cases_scored": len(scores),
                "status": (
                    "passed" if scored and sum(scored) / len(scored) >= 0.5
                    else ("failed" if scored else "no-data")
                ),
            }
        )

    payload: dict[str, Any] = {
        "summary": summary,
        "total_traces_scored": len({row[3] for row in rows}),
    }
    if per_trace:
        payload["per_trace"] = per_trace_rows
    return payload


@router.get("/rag/{trace_id}")
def rag_metrics_for_trace(trace_id: str) -> dict[str, Any]:
    """All stored judge results for one trace."""

    with session_scope() as session:
        trace = session.get(Trace, trace_id)
        if trace is None:
            return {"error": "trace not found"}
        results = session.scalars(
            select(EvalResult).where(EvalResult.trace_id == trace_id)
        ).all()
        return {
            "trace_id": trace_id,
            "trace_name": trace.name,
            "results": [
                {
                    "metric_name": r.metric_name,
                    "score": r.score,
                    "status": r.status,
                    "reasoning": r.reasoning,
                }
                for r in results
            ],
        }
