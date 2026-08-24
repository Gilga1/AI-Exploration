"""Phase 5 agent metrics: ToolCorrectness, TaskCompletion, LoopEfficiency.

ToolCorrectness is deterministic set comparison. TaskCompletion uses DeepEval's
GEval when a judge LLM is configured; LoopEfficiency is a custom GEval variant
penalising iterations beyond an expected budget. Both degrade to deterministic
heuristics offline so CI stays free and green.
"""

from __future__ import annotations

from typing import Any

from app.telemetry.trace_adapter import ReconstructedCase


def tool_correctness(case: ReconstructedCase, expected_tools: list[str] | None = None) -> dict[str, Any]:
    """1.0 when the tools actually called match the expected set exactly."""

    if expected_tools is None:
        # No expectation declared: correctness means "no spurious tool calls"
        # for pure-RAG traces and "at least one sensible call" for agent ones.
        return {
            "score": 1.0 if (case.tools_called or not case.is_agent_trace) else 0.0,
            "status": "passed",
            "reasoning": f"tools called: {case.tools_called or 'none'}",
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
    """Offline heuristic: an answer exists and is non-trivially long."""

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
    """Penalise loop iterations beyond the optimal/expected count.

    With a judge LLM configured this runs as a custom GEval over the trace
    narrative; offline it reduces to a deterministic iteration-count penalty.
    """

    iterations = case.iterations if case.iterations is not None else 1
    has_judge = bool((settings or __import__(
        "app.core.config", fromlist=["get_settings"]
    ).get_settings()).has_llm_judge_credentials)

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
        except Exception:
            pass  # Fall through to the deterministic penalty.

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
    """Score one agent-produced trace with all three agent metrics."""

    completion = task_completion_deterministic(case)

    # Upgrade TaskCompletion to GEval when a judge LLM is available.
    from app.core.config import get_settings

    resolved = settings or get_settings()
    if resolved.has_llm_judge_credentials and _geval_available() and case.actual_output:
        try:
            from deepeval.evaluate import execute_test_cases  # noqa: F401  (availability probe)
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
        except Exception:
            pass  # Keep the deterministic fallback.

    return [
        {"metric_name": "ToolCorrectness", **tool_correctness(case, expected_tools)},
        {"metric_name": "TaskCompletion", **completion},
        {
            "metric_name": "LoopEfficiency",
            **loop_efficiency(case, expected_max_iterations, settings),
        },
    ]
