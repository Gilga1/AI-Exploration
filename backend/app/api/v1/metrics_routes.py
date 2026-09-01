"""Aggregated and per-trace RAG metric reporting for the dashboard."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from app.core.auth import require_api_key
from app.core.config import get_settings
from app.db.models import EvalResult, Trace
from app.db.session import session_scope
from app.evaluation.alerting import check_score_thresholds
from app.evaluation.runners.realtime_worker import score_pending_traces

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"], dependencies=[Depends(require_api_key)])

RAG_METRIC_NAMES = ("Faithfulness", "ContextualPrecision", "ContextualRecall", "Hallucination")
AGENT_METRIC_NAMES = ("ToolCorrectness", "TaskCompletion", "LoopEfficiency")


@router.get("/rag")
def rag_metrics(per_trace: bool = False) -> dict[str, Any]:
    settings = get_settings()
    if settings.metrics_score_backstop:
        try:
            score_pending_traces(limit=25)
        except Exception:
            logger.warning("metrics score backstop failed", exc_info=True)

    with session_scope() as session:
        summary_rows = session.execute(
            select(
                EvalResult.metric_name,
                func.avg(EvalResult.score),
                func.count(EvalResult.id),
            )
            .where(EvalResult.metric_name.in_(RAG_METRIC_NAMES))
            .where(EvalResult.score.is_not(None))
            .group_by(EvalResult.metric_name)
        ).all()
        total_traces_scored = session.scalar(
            select(func.count(func.distinct(EvalResult.trace_id))).where(
                EvalResult.metric_name.in_(RAG_METRIC_NAMES)
            )
        ) or 0

        per_trace_rows: list[dict[str, Any]] = []
        if per_trace:
            limit = settings.metrics_per_trace_limit
            per_trace_rows = [
                {
                    "trace_id": trace_id,
                    "metric": metric_name,
                    "score": score,
                    "status": status,
                    "reasoning": reasoning,
                    "scored_at": created_at.isoformat() if created_at else None,
                }
                for metric_name, score, status, trace_id, reasoning, created_at in session.execute(
                    select(
                        EvalResult.metric_name,
                        EvalResult.score,
                        EvalResult.status,
                        EvalResult.trace_id,
                        EvalResult.reasoning,
                        EvalResult.created_at,
                    )
                    .where(EvalResult.metric_name.in_(RAG_METRIC_NAMES))
                    .order_by(EvalResult.created_at.desc())
                    .limit(limit)
                ).all()
            ]

    by_metric = {name: (avg_score, count) for name, avg_score, count in summary_rows}
    summary = []
    for name in RAG_METRIC_NAMES:
        avg_score, count = by_metric.get(name, (None, 0))
        scored_avg = float(avg_score) if avg_score is not None else None
        summary.append(
            {
                "name": name,
                "avg_score": round(scored_avg, 4) if scored_avg is not None else None,
                "cases_scored": int(count),
                "status": (
                    "passed" if scored_avg is not None and scored_avg >= 0.5
                    else ("failed" if scored_avg is not None else "no-data")
                ),
            }
        )

    payload: dict[str, Any] = {
        "summary": summary,
        "total_traces_scored": int(total_traces_scored),
    }
    if per_trace:
        payload["per_trace"] = list(reversed(per_trace_rows))

    try:
        breaches = check_score_thresholds()
        if breaches:
            payload["alerts"] = breaches
    except Exception:
        logger.warning("alert threshold check failed", exc_info=True)

    return payload


@router.get("/rag/{trace_id}")
def rag_metrics_for_trace(trace_id: str) -> dict[str, Any]:
    with session_scope() as session:
        trace = session.get(Trace, trace_id)
        if trace is None:
            raise HTTPException(status_code=404, detail="Trace not found")
        results = session.scalars(
            select(EvalResult).where(EvalResult.trace_id == trace_id)
        ).all()
        return {
            "trace_id": trace_id,
            "trace_name": trace.name,
            "results": [
                {
                    "metric_name": result.metric_name,
                    "score": result.score,
                    "status": result.status,
                    "reasoning": result.reasoning,
                }
                for result in results
            ],
        }


@router.get("/agent")
def agent_metrics() -> dict[str, Any]:
    with session_scope() as session:
        summary_rows = session.execute(
            select(
                EvalResult.metric_name,
                func.avg(EvalResult.score),
                func.count(EvalResult.id),
            )
            .where(EvalResult.metric_name.in_(AGENT_METRIC_NAMES))
            .where(EvalResult.score.is_not(None))
            .group_by(EvalResult.metric_name)
        ).all()
        rows = session.execute(
            select(
                EvalResult.metric_name,
                EvalResult.score,
                EvalResult.status,
                EvalResult.trace_id,
            ).where(EvalResult.metric_name.in_(AGENT_METRIC_NAMES))
        ).all()

    by_metric = {name: (avg_score, count) for name, avg_score, count in summary_rows}
    summary = []
    for name in AGENT_METRIC_NAMES:
        avg_score, count = by_metric.get(name, (None, 0))
        scored_avg = float(avg_score) if avg_score is not None else None
        summary.append(
            {
                "name": name,
                "avg_score": round(scored_avg, 4) if scored_avg is not None else None,
                "cases_scored": int(count),
                "status": (
                    "passed" if scored_avg is not None and scored_avg >= 0.5
                    else ("failed" if scored_avg is not None else "no-data")
                ),
            }
        )

    tool_scores: dict[str, float] = {}
    completion_by_trace: dict[str, float] = {}
    loop_by_trace: dict[str, float] = {}
    for metric_name, score, _status, trace_id in rows:
        if score is None:
            continue
        if metric_name == "ToolCorrectness":
            tool_scores[trace_id] = score
        elif metric_name == "TaskCompletion":
            completion_by_trace[trace_id] = score
        elif metric_name == "LoopEfficiency":
            loop_by_trace[trace_id] = score

    runs = []
    for trace_id in sorted(tool_scores | completion_by_trace | loop_by_trace):
        completion = completion_by_trace.get(trace_id)
        loop = loop_by_trace.get(trace_id)
        if completion is None or loop is None:
            classification = "unknown"
        elif completion >= 0.5 and loop >= 0.75:
            classification = "efficient"
        else:
            classification = "thrashing"
        runs.append(
            {
                "trace_id": trace_id,
                "tool_correctness": tool_scores.get(trace_id),
                "task_success": completion is not None and completion >= 0.5,
                "loop_efficiency": loop,
                "classification": classification,
            }
        )

    return {
        "summary": summary,
        "total_agent_traces_scored": len(runs),
        "runs": runs,
    }
