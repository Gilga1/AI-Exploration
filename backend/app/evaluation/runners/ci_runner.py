"""Run the Phase 1 golden dataset and produce an API-friendly scorecard."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from app.core.config import Settings, get_settings
from app.evaluation.datasets.golden_dataset import GOLDEN_DATASET, GoldenExample
from app.rag.chains import RAGResult, build_phase_one_chain

METRIC_NAMES = (
    "Faithfulness",
    "ContextualPrecision",
    "ContextualRecall",
    "Hallucination",
)


def deepeval_is_available() -> bool:
    """Avoid making DeepEval a runtime import requirement for the API shell."""

    try:
        import deepeval  # noqa: F401
    except ImportError:
        return False
    return True


def make_deepeval_test_case(example: GoldenExample, result: RAGResult) -> Any:
    """Build the standard DeepEval payload only when the package is installed."""

    from deepeval.test_case import LLMTestCase

    return LLMTestCase(
        input=example.query,
        actual_output=result.answer,
        expected_output=example.expected_answer,
        retrieval_context=result.contexts,
    )


def build_rag_metrics() -> list[tuple[str, Any]]:
    """Construct Phase 1's four required DeepEval metrics."""

    from deepeval.metrics import (
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        FaithfulnessMetric,
        HallucinationMetric,
    )

    return [
        ("Faithfulness", FaithfulnessMetric(threshold=0.5, include_reason=True)),
        (
            "ContextualPrecision",
            ContextualPrecisionMetric(threshold=0.5, include_reason=True),
        ),
        ("ContextualRecall", ContextualRecallMetric(threshold=0.5, include_reason=True)),
        ("Hallucination", HallucinationMetric(threshold=0.5, include_reason=True)),
    ]


def _skipped_metrics(reason: str) -> list[dict[str, Any]]:
    return [
        {"name": name, "status": "skipped", "score": None, "reason": reason}
        for name in METRIC_NAMES
    ]


def _run_judges(executions: list[tuple[GoldenExample, RAGResult]]) -> list[dict[str, Any]]:
    """Score every result and aggregate each DeepEval metric's numeric result."""

    aggregate: dict[str, list[float]] = defaultdict(list)
    successes: dict[str, list[bool]] = defaultdict(list)
    errors: dict[str, list[str]] = defaultdict(list)
    for example, result in executions:
        test_case = make_deepeval_test_case(example, result)
        for name, metric in build_rag_metrics():
            try:
                metric.measure(test_case)
                if metric.score is not None:
                    aggregate[name].append(float(metric.score))
                    successes[name].append(bool(getattr(metric, "success", True)))
            except Exception as exc:  # Individual judge failure must not kill /eval/run.
                errors[name].append(str(exc))

    scorecard: list[dict[str, Any]] = []
    for name in METRIC_NAMES:
        scores = aggregate[name]
        if scores:
            passed = all(successes[name]) and not errors[name]
            scorecard.append(
                {
                    "name": name,
                    "status": "passed" if passed else "partial",
                    "score": round(sum(scores) / len(scores), 4),
                    "cases_scored": len(scores),
                }
            )
        else:
            scorecard.append(
                {
                    "name": name,
                    "status": "failed",
                    "score": None,
                    "reason": errors[name][0] if errors[name] else "No score returned",
                }
            )
    return scorecard


def run_golden_dataset(settings: Settings | None = None) -> dict[str, Any]:
    """Run deterministic RAG retrieval and, when configured, DeepEval judges."""

    resolved_settings = settings or get_settings()
    chain = build_phase_one_chain(resolved_settings)
    executions = [(example, chain.invoke(example.query)) for example in GOLDEN_DATASET]

    if not resolved_settings.has_llm_judge_credentials:
        metrics = _skipped_metrics("No LLM judge API key is configured; offline RAG completed.")
    elif not deepeval_is_available():
        metrics = _skipped_metrics("DeepEval is not installed in this environment.")
    else:
        metrics = _run_judges(executions)

    statuses = {metric["status"] for metric in metrics}
    if statuses == {"passed"}:
        status = "completed"
    elif statuses == {"skipped"}:
        status = "skipped"
    else:
        status = "partial"
    return {
        "status": status,
        "dataset": "phase-1-golden-dataset",
        "total_cases": len(executions),
        "llm_provider": executions[0][1].llm_provider if executions else "unknown",
        "metrics": metrics,
        "cases": [
            {
                "id": example.id,
                "query": example.query,
                "answer": result.answer,
                "source_ids": result.source_ids,
            }
            for example, result in executions
        ],
    }


def main() -> None:
    """Allow local use with ``python -m app.evaluation.runners.ci_runner``."""

    print(json.dumps(run_golden_dataset(), indent=2))


if __name__ == "__main__":
    main()
