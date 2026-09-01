"""Run the Phase 1 golden dataset and produce an API-friendly scorecard."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from app.core.config import Settings, get_settings
from app.core.llm import configure_llm_environment
from app.evaluation.datasets.golden_dataset import GOLDEN_DATASET, GoldenExample
from app.rag.chains import RAGResult, build_phase_one_chain
from app.telemetry.callback_bridge import LangChainOTelCallbackHandler

METRIC_NAMES = (
    "Faithfulness",
    "ContextualPrecision",
    "ContextualRecall",
    "Hallucination",
)

_RAG_METRICS: list[tuple[str, Any]] | None = None


def deepeval_is_available() -> bool:
    try:
        import deepeval  # noqa: F401
    except ImportError:
        return False
    return True


def make_deepeval_test_case(example: GoldenExample, result: RAGResult) -> Any:
    from deepeval.test_case import LLMTestCase

    return LLMTestCase(
        input=example.query,
        actual_output=result.answer,
        expected_output=example.expected_answer,
        retrieval_context=result.contexts,
    )


def build_rag_metrics() -> list[tuple[str, Any]]:
    global _RAG_METRICS
    if _RAG_METRICS is not None:
        return _RAG_METRICS

    from deepeval.metrics import (
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        FaithfulnessMetric,
        HallucinationMetric,
    )

    _RAG_METRICS = [
        ("Faithfulness", FaithfulnessMetric(threshold=0.5, include_reason=True)),
        ("ContextualPrecision", ContextualPrecisionMetric(threshold=0.5, include_reason=True)),
        ("ContextualRecall", ContextualRecallMetric(threshold=0.5, include_reason=True)),
        ("Hallucination", HallucinationMetric(threshold=0.5, include_reason=True)),
    ]
    return _RAG_METRICS


def _skipped_metrics(reason: str) -> list[dict[str, Any]]:
    return [
        {"name": name, "status": "skipped", "score": None, "reason": reason}
        for name in METRIC_NAMES
    ]


def _run_judges(executions: list[tuple[GoldenExample, RAGResult]]) -> list[dict[str, Any]]:
    aggregate: dict[str, list[float]] = defaultdict(list)
    successes: dict[str, list[bool]] = defaultdict(list)
    errors: dict[str, list[str]] = defaultdict(list)
    metrics = build_rag_metrics()
    for example, result in executions:
        test_case = make_deepeval_test_case(example, result)
        for name, metric in metrics:
            try:
                metric.measure(test_case)
                if metric.score is not None:
                    aggregate[name].append(float(metric.score))
                    successes[name].append(bool(getattr(metric, "success", True)))
            except Exception as exc:
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
    resolved_settings = settings or get_settings()
    configure_llm_environment(resolved_settings)
    callback_handler = LangChainOTelCallbackHandler()
    chain = build_phase_one_chain(resolved_settings, callback_handler=callback_handler)
    executions = [(example, chain.invoke(example.query)) for example in GOLDEN_DATASET]
    trace_ids = [
        result.trace_id or callback_handler.last_completed_trace_id()
        for _, result in executions
    ]
    trace_ids = [trace_id for trace_id in trace_ids if trace_id]

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
        "trace_ids": trace_ids,
        "cases": [
            {
                "id": example.id,
                "query": example.query,
                "answer": result.answer,
                "source_ids": result.source_ids,
                "trace_id": result.trace_id,
            }
            for example, result in executions
        ],
    }


def main() -> None:
    print(json.dumps(run_golden_dataset(), indent=2))


if __name__ == "__main__":
    main()
