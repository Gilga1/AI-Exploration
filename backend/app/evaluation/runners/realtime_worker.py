"""Async eval worker: score completed traces without touching the hot path."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.llm import configure_llm_environment
from app.db.models import EvalResult, Span, Trace
from app.db.session import session_scope
from app.evaluation.expectations import expected_answer_for_question, expected_for_question
from app.telemetry.trace_adapter import ReconstructedCase, reconstruct_test_case

logger = logging.getLogger(__name__)

RAG_METRIC_NAMES = (
    "Faithfulness",
    "ContextualPrecision",
    "ContextualRecall",
    "Hallucination",
)
AGENT_METRIC_NAMES = ("ToolCorrectness", "TaskCompletion", "LoopEfficiency")


def should_sample(trace_id: str, rate: float | None = None) -> bool:
    resolved = rate if rate is not None else get_settings().eval_sampling_rate
    if resolved >= 1.0:
        return True
    if resolved <= 0.0:
        return False
    try:
        stable = int(trace_id[:8], 16) / float(0xFFFFFFFF)
    except ValueError:
        digest = hashlib.sha256(trace_id.encode("utf-8")).hexdigest()
        stable = int(digest[:8], 16) / float(0xFFFFFFFF)
    return stable < resolved


def _expected_metric_names(case: ReconstructedCase, settings) -> set[str]:
    names = set(RAG_METRIC_NAMES) if case.actual_output is not None else set()
    if case.is_agent_trace:
        names.update(AGENT_METRIC_NAMES)
    if not settings.has_llm_judge_credentials:
        return set()
    if case.actual_output is None:
        return set()
    if not case.retrieval_context and not case.is_agent_trace:
        return names & set(AGENT_METRIC_NAMES)
    return names


def _run_rag_judges(case: Any, expected_output: str | None) -> list[dict[str, Any]]:
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
        expected_output=expected_output,
        retrieval_context=case.retrieval_context or [],
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
        except Exception as exc:
            logger.warning("Judge %s failed on trace scoring: %s", name, exc)
            results.append(
                {
                    "metric_name": name,
                    "score": None,
                    "status": "failed",
                    "reasoning": f"judge error: {exc}",
                }
            )
    return results


def _skipped_results(reason: str, metric_names: set[str]) -> list[dict[str, Any]]:
    return [
        {"metric_name": name, "score": None, "status": "skipped", "reasoning": reason}
        for name in sorted(metric_names)
    ]


def _score_agent_case(case: ReconstructedCase, settings=None) -> list[dict[str, Any]]:
    from app.evaluation.metrics.agent_metrics import run_agent_metrics

    expected_tools, max_iterations = expected_for_question(case.input)
    return run_agent_metrics(
        case,
        expected_tools=expected_tools,
        expected_max_iterations=max_iterations,
        settings=settings,
    )


def _upsert_eval_result(session, trace_id: str, row: dict[str, Any]) -> EvalResult:
    existing = session.scalar(
        select(EvalResult).where(
            EvalResult.trace_id == trace_id,
            EvalResult.metric_name == row["metric_name"],
        )
    )
    if existing:
        existing.score = row.get("score")
        existing.status = row["status"]
        existing.reasoning = row.get("reasoning")
        return existing

    result = EvalResult(
        trace_id=trace_id,
        metric_name=row["metric_name"],
        score=row.get("score"),
        status=row["status"],
        reasoning=row.get("reasoning"),
    )
    session.add(result)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(
            select(EvalResult).where(
                EvalResult.trace_id == trace_id,
                EvalResult.metric_name == row["metric_name"],
            )
        )
        if existing:
            existing.score = row.get("score")
            existing.status = row["status"]
            existing.reasoning = row.get("reasoning")
            return existing
        raise
    return result


def score_trace(trace_id: str, settings=None) -> list[dict[str, Any]]:
    resolved_settings = settings or get_settings()
    configure_llm_environment(resolved_settings)

    with session_scope() as session:
        trace = session.get(Trace, trace_id)
        if trace is None:
            logger.warning("score_trace called for unknown trace %s", trace_id)
            return []

        spans = session.scalars(
            select(Span).where(Span.trace_id == trace_id).order_by(Span.start_time.asc())
        ).all()
        case = reconstruct_test_case(trace_id, spans)

        existing_rows = session.scalars(
            select(EvalResult).where(EvalResult.trace_id == trace_id)
        ).all()
        existing_by_name = {row.metric_name: row for row in existing_rows}
        expected_names = _expected_metric_names(case, resolved_settings)
        if expected_names and expected_names.issubset(existing_by_name):
            return [_result_payload(result) for result in existing_rows]

        missing_names = expected_names - set(existing_by_name)
        if not missing_names and existing_rows:
            return [_result_payload(result) for result in existing_rows]

        if case.actual_output is None:
            rows = _skipped_results("Trace missing answer.", expected_names or set(RAG_METRIC_NAMES))
        elif not resolved_settings.has_llm_judge_credentials:
            rows = _skipped_results(
                "No LLM judge API key configured; trace captured but not judged.",
                expected_names,
            )
            if case.is_agent_trace:
                rows += _score_agent_case(case, resolved_settings)
        else:
            rows = []
            rag_names = missing_names & set(RAG_METRIC_NAMES)
            if rag_names:
                expected_output = expected_answer_for_question(case.input)
                try:
                    rows.extend(_run_rag_judges(case, expected_output))
                except ImportError:
                    rows.extend(
                        _skipped_results(
                            "DeepEval is not installed in this environment.",
                            rag_names,
                        )
                    )
            if case.is_agent_trace and (missing_names & set(AGENT_METRIC_NAMES)):
                rows.extend(_score_agent_case(case, resolved_settings))

        persisted: list[EvalResult] = []
        for row in rows:
            if row["metric_name"] not in missing_names and row["metric_name"] in existing_by_name:
                persisted.append(existing_by_name[row["metric_name"]])
                continue
            persisted.append(_upsert_eval_result(session, trace_id, row))

    return [_result_payload(result) for result in persisted]


def score_pending_traces(limit: int = 25) -> list[str]:
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
