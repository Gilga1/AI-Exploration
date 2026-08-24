"""Async eval worker: score completed traces without touching the hot path.

In dev this runs as a FastAPI BackgroundTask right after the response is sent.
In production the same ``score_trace`` entrypoint can be consumed from a Celery
worker or a queue consumer — the function only needs ``(trace_id)``.
"""

from __future__ import annotations

import logging
import random
from typing import Any

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import EvalResult, Span, Trace
from app.db.session import session_scope
from app.telemetry.trace_adapter import reconstruct_test_case

logger = logging.getLogger(__name__)


def should_sample(trace_id: str, rate: float | None = None) -> bool:
    """Deterministic per-trace sampling so retries do not double-score."""

    resolved = rate if rate is not None else get_settings().eval_sampling_rate
    if resolved >= 1.0:
        return True
    if resolved <= 0.0:
        return False
    # First 8 hex chars of the trace id give a stable 0..1 value in [0,1).
    try:
        stable = int(trace_id[:8], 16) / float(0xFFFFFFFF)
    except ValueError:
        stable = random.random()
    return stable < resolved


def _run_rag_judges(case: Any) -> list[dict[str, Any]]:
    """Score one reconstructed case with the Phase 1 DeepEval metrics."""

    results: list[dict[str, Any]] = []
    from deepeval.metrics import (
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        FaithfulnessMetric,
        HallucinationMetric,
    )
    from deepeval.test_case import LLMTestCase

    test_case = LLMTestCase(
        input=case.input,
        actual_output=case.actual_output or "",
        retrieval_context=case.retrieval_context,
    )

    metric_specs = [
        ("Faithfulness", FaithfulnessMetric(threshold=0.5, include_reason=True)),
        ("ContextualPrecision", ContextualPrecisionMetric(threshold=0.5, include_reason=True)),
        ("ContextualRecall", ContextualRecallMetric(threshold=0.5, include_reason=True)),
        ("Hallucination", HallucinationMetric(threshold=0.5, include_reason=True)),
    ]
    for name, metric in metric_specs:
        try:
            metric.measure(test_case)
            results.append(
                {
                    "metric_name": name,
                    "score": float(metric.score) if metric.score is not None else None,
                    "status": "passed" if getattr(metric, "success", True) else "failed",
                    "reasoning": getattr(metric, "reason", None),
                }
            )
        except Exception as exc:  # One judge failing must not block the others.
            logger.warning("Judge %s failed on trace scoring: %s", name, exc)
            results.append({"metric_name": name, "score": None, "status": "failed",
                            "reasoning": f"judge error: {exc}"})
    return results


def _skipped_results(reason: str) -> list[dict[str, Any]]:
    return [
        {"metric_name": name, "score": None, "status": "skipped", "reasoning": reason}
        for name in ("Faithfulness", "ContextualPrecision", "ContextualRecall", "Hallucination")
    ]


def score_trace(trace_id: str, settings=None) -> list[dict[str, Any]]:
    """Reconstruct and score one trace; persist EvalResults keyed by trace_id.

    Never raises into the caller's request path — errors are logged and recorded
    as failed EvalResults so dashboards can surface them.
    """

    resolved_settings = settings or get_settings()

    with session_scope() as session:
        trace = session.get(Trace, trace_id)
        if trace is None:
            logger.warning("score_trace called for unknown trace %s", trace_id)
            return []

        existing = session.scalars(
            select(EvalResult).where(EvalResult.trace_id == trace_id)
        ).all()
        if existing:
            return [_result_payload(result) for result in existing]

        spans = session.scalars(
            select(Span).where(Span.trace_id == trace_id).order_by(Span.start_time.asc())
        ).all()
        case = reconstruct_test_case(trace_id, spans)

        if case.actual_output is None or not case.retrieval_context:
            rows = _skipped_results("Trace missing answer or retrieval context.")
        elif not resolved_settings.has_llm_judge_credentials:
            rows = _skipped_results("No LLM judge API key configured; trace captured but not judged.")
        else:
            try:
                rows = _run_rag_judges(case)
            except ImportError:
                rows = _skipped_results("DeepEval is not installed in this environment.")

        persisted: list[EvalResult] = []
        for row in rows:
            result = EvalResult(
                trace_id=trace_id,
                metric_name=row["metric_name"],
                score=row.get("score"),
                status=row["status"],
                reasoning=row.get("reasoning"),
            )
            session.add(result)
            persisted.append(result)

    return [_result_payload(result) for result in persisted]


def score_pending_traces(limit: int = 25) -> list[str]:
    """Sweep unscored traces — useful as a periodic backstop job."""

    scored: list[str] = []
    with session_scope() as session:
        trace_ids = session.scalars(
            select(Trace.id)
            .outerjoin(EvalResult, EvalResult.trace_id == Trace.id)
            .where(EvalResult.id.is_(None))
            .limit(limit)
        ).all()
    for trace_id in trace_ids:
        if should_sample(trace_id):
            score_trace(trace_id)
            scored.append(trace_id)
    return scored


def _result_payload(result: EvalResult) -> dict[str, Any]:
    return {
        "trace_id": result.trace_id,
        "metric_name": result.metric_name,
        "score": result.score,
        "status": result.status,
        "reasoning": result.reasoning,
    }
