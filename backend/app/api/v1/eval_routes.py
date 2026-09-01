"""Manual endpoint for the Phase 1 offline golden-dataset evaluation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends

from app.core.auth import require_api_key
from app.core.config import get_settings
from app.evaluation.runners.ci_runner import run_golden_dataset
from app.evaluation.runners.realtime_worker import score_trace, should_sample

router = APIRouter(
    prefix="/eval",
    tags=["evaluations"],
    dependencies=[Depends(require_api_key)],
)


@router.post("/run")
def run_evaluation(background_tasks: BackgroundTasks) -> dict[str, Any]:
    scorecard = run_golden_dataset()
    settings = get_settings()

    for trace_id in scorecard.get("trace_ids", []):
        if should_sample(trace_id, rate=settings.eval_sampling_rate):
            background_tasks.add_task(score_trace, trace_id)

    return scorecard
