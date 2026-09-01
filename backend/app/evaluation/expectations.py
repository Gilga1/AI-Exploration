"""Centralized golden expectations for CI and realtime scoring."""

from __future__ import annotations

from app.evaluation.datasets.golden_dataset import AGENT_GOLDEN_SCENARIOS, GOLDEN_DATASET


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


def expected_for_question(question: str) -> tuple[list[str], int]:
    """Return (expected_tools, max_iterations) for a captured agent question."""

    normalised = _normalise(question)
    for scenario in AGENT_GOLDEN_SCENARIOS:
        if _normalise(scenario.query) == normalised:
            return list(scenario.expected_tools), scenario.expected_max_iterations

    lowered = question.lower()
    if "calculate" in lowered or any(char in question for char in "+-*/"):
        return ["calculator"], 2
    if any(token in lowered for token in ("look up", "lookup", "find the doc")):
        return ["document_lookup"], 3

    return [], 3


def expected_answer_for_question(question: str) -> str | None:
    """Lookup the golden expected answer when the input matches a dataset row."""

    normalised = _normalise(question)
    for example in GOLDEN_DATASET:
        if _normalise(example.query) == normalised:
            return example.expected_answer
    return None
