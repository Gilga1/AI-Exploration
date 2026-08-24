"""Manual endpoint for the Phase 1 offline golden-dataset evaluation.

Phase 3 addition: after the scorecard is computed, each invocation has produced
a captured trace. Scoring those traces is dispatched as a background task so
the HTTP response never waits on LLM-judge metrics.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends

from app.core.auth import require_api_key
from app.core.config import get_settings
from app.db.session import session_scope
from app.evaluation.runners.ci_runner import run_golden_dataset
from app.evaluation.runners.realtime_worker import score_trace, should_sample

router = APIRouter(
    prefix="/eval",
    tags=["evaluations"],
    # M4: /run fans out to paid LLM calls — never expose it unauthenticated.
    dependencies=[Depends(require_api_key)],
)


def _latest_unscored_trace_ids() -> list[str]:
    """Traces created by this run that have not been scored yet."""

    from sqlalchemy import select

    from app.db.models import EvalResult, Trace

    with session_scope() as session:
        trace_ids = session.scalars(
            select(Trace.id)
            .outerjoin(EvalResult, EvalResult.trace_id == Trace.id)
            .where(EvalResult.id.is_(None))
            .order_by(Trace.start_time.desc())
            .limit(50)
        ).all()
    return list(trace_ids)


@router.post("/run")
def run_evaluation(background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Run Phase 1 retrieval and return judge scores (or offline skips)."""

    scorecard = run_golden_dataset()

    settings = get_settings()
    for trace_id in _latest_unscored_trace_ids():
        if should_sample(trace_id, rate=settings.eval_sampling_rate):
            # Async eval pipeline: scoring happens off the response path.
            background_tasks.add_task(score_trace, trace_id)

    return scorecard
