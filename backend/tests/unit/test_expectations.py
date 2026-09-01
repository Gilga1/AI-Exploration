"""Unit tests that always run in CI without LLM credentials."""

from __future__ import annotations

import pytest
from app.core.config import Settings
from app.core.llm import get_chat_model
from app.evaluation.expectations import expected_answer_for_question, expected_for_question
from app.evaluation.metrics.agent_metrics import tool_correctness
from app.telemetry.trace_adapter import ReconstructedCase


def test_expected_for_rag_question_has_no_tools() -> None:
    tools, max_iterations = expected_for_question("What does Acme Orbit sell?")
    assert tools == []
    assert max_iterations == 3


def test_expected_answer_lookup() -> None:
    answer = expected_answer_for_question("What does Acme Orbit sell?")
    assert answer is not None
    assert "OrbitNote" in answer


def test_tool_correctness_without_expected_tools() -> None:
    case = ReconstructedCase(
        input="What does Acme Orbit sell?",
        actual_output="Acme Orbit sells notebooks.",
        retrieval_context=["context"],
        document_ids=["company-overview"],
        tools_called=[],
        llm_provider="openrouter",
        model="openai/gpt-4o-mini",
        duration_ms=10.0,
        is_agent_trace=True,
    )
    result = tool_correctness(case, expected_tools=[])
    assert result["score"] == 1.0


def test_missing_llm_key_fails_fast() -> None:
    keyless = Settings(
        llm_api_key="",
        llm_model="openai/gpt-4o-mini",
        llm_base_url="https://openrouter.ai/api/v1",
        database_url="sqlite:///./test.db",
        _env_file=None,
    )
    with pytest.raises(RuntimeError, match="LLM API key"):
        get_chat_model(keyless)
