"""Manual endpoint for the Phase 1 offline golden-dataset evaluation."""

from typing import Any

from fastapi import APIRouter

from app.evaluation.runners.ci_runner import run_golden_dataset

router = APIRouter(prefix="/eval", tags=["evaluations"])


@router.post("/run")
def run_evaluation() -> dict[str, Any]:
    """Run Phase 1 retrieval and return judge scores (or offline skips)."""

    return run_golden_dataset()
