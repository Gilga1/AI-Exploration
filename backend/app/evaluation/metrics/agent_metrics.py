"""Phase 5 agent metrics: ToolCorrectness, TaskCompletion, LoopEfficiency."""

from __future__ import annotations

import logging
from typing import Any

from app.telemetry.trace_adapter import ReconstructedCase

logger = logging.getLogger(__name__)


def tool_correctness(case: ReconstructedCase, expected_tools: list[str] | None = None) -> dict[str, Any]:
    """1.0 when the tools actually called match the expected set exactly."""

    if expected_tools is None:
        expected_tools = []

    if not expected_tools:
        score = 1.0 if not case.tools_called else 0.0
        return {
            "score": score,
            "status": "passed" if score >= 0.99 else "failed",
            "reasoning": f"no tools expected; called {case.tools_called or 'none'}",
        }

    actual_set, expected_set = set(case.tools_called), set(expected_tools)
    score = 1.0 if actual_set == expected_set else (
        len(actual_set & expected_set) / len(actual_set | expected_set)
    )
    return {
        "score": round(score, 4),
        "status": "passed" if score >= 0.99 else ("failed" if score < 0.5 else "partial"),
        "reasoning": f"expected {sorted(expected_set)}, called {sorted(actual_set)}",
    }


def task_completion_deterministic(case: ReconstructedCase) -> dict[str, Any]:
    answer = case.actual_output or ""
    ok = len(answer.split()) >= 3
    return {
        "score": 1.0 if ok else 0.0,
        "status": "passed" if ok else "failed",
        "reasoning": (
            f"answer present ({len(answer.split())} words)"
            if ok else "no substantive answer produced"
        ),
    }


def _geval_available() -> bool:
    try:
        import deepeval  # noqa: F401

        return True
    except ImportError:
        return False


def loop_efficiency(
    case: ReconstructedCase,
    expected_max_iterations: int = 3,
    settings=None,
) -> dict[str, Any]:
    iterations = case.iterations if case.iterations is not None else 1
    from app.core.config import get_settings

    resolved = settings or get_settings()
    has_judge = bool(resolved.has_llm_judge_credentials)

    if has_judge and _geval_available():
        try:
            from deepeval.metrics import GEval
            from deepeval.test_case import LLMTestCase, LLMTestCaseParams

            metric = GEval(
                name="Loop Efficiency",
                criteria=(
                    "Evaluate whether the agent solved the task in a reasonable number of "
                    "steps without redundant tool calls, repeated retrievals, or thrashing. "
                    f"The expected maximum number of loop iterations is {expected_max_iterations}."
                ),
                evaluation_params=[
                    LLMTestCaseParams.INPUT,
                    LLMTestCaseParams.ACTUAL_OUTPUT,
                ],
                threshold=0.5,
                include_reason=True,
            )
            narrative = (
                f"Iterations used: {iterations}. Tools called: {case.tools_called or 'none'}. "
                f"Final answer: {case.actual_output}"
            )
            test_case = LLMTestCase(input=case.input, actual_output=narrative)
            metric.measure(test_case)
            if metric.score is not None:
                return {
                    "score": float(metric.score),
                    "status": "passed" if metric.success else "failed",
                    "reasoning": getattr(metric, "reason", None),
                }
        except Exception as exc:
            logger.warning("LoopEfficiency GEval failed: %s", exc, exc_info=True)

    excess = max(0, iterations - expected_max_iterations)
    score = max(0.0, 1.0 - 0.25 * excess)
    return {
        "score": round(score, 4),
        "status": "passed" if excess == 0 else ("partial" if excess <= 2 else "failed"),
        "reasoning": (
            f"{iterations} iterations vs expected ≤{expected_max_iterations}"
            + (f" ({excess} extra)" if excess else "")
        ),
    }


def run_agent_metrics(
    case: ReconstructedCase,
    expected_tools: list[str] | None = None,
    expected_max_iterations: int = 3,
    settings=None,
) -> list[dict[str, Any]]:
    completion = task_completion_deterministic(case)

    from app.core.config import get_settings

    resolved = settings or get_settings()
    if resolved.has_llm_judge_credentials and _geval_available() and case.actual_output:
        try:
            from deepeval.metrics import GEval
            from deepeval.test_case import LLMTestCase, LLMTestCaseParams

            metric = GEval(
                name="Task Completion",
                criteria=(
                    "Given the user's question and the agent's final answer, determine "
                    "whether the answer fully and correctly addresses the question."
                ),
                evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
                threshold=0.5,
                include_reason=True,
            )
            metric.measure(LLMTestCase(input=case.input, actual_output=case.actual_output))
            if metric.score is not None:
                completion = {
                    "score": float(metric.score),
                    "status": "passed" if metric.success else "failed",
                    "reasoning": getattr(metric, "reason", None),
                }
        except Exception as exc:
            logger.warning("TaskCompletion GEval failed: %s", exc, exc_info=True)

    return [
        {"metric_name": "ToolCorrectness", **tool_correctness(case, expected_tools)},
        {"metric_name": "TaskCompletion", **completion},
        {
            "metric_name": "LoopEfficiency",
            **loop_efficiency(case, expected_max_iterations, settings),
        },
    ]
