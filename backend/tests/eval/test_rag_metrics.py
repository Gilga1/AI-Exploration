"""Regression gate for the golden dataset.

The harness is fully LLM-driven: generation and judging both require
``OPENAI_API_KEY``. When the key is absent the module skips — safe for
untrusted/offline CI; when present, every golden case runs against the real
model and DeepEval judges assert the RAG metric thresholds.
"""

from __future__ import annotations

import pytest

deepeval = pytest.importorskip("deepeval", reason="DeepEval is an evaluation extra")
from deepeval import assert_test

from app.core.config import get_settings
from app.evaluation.datasets.golden_dataset import GOLDEN_DATASET, GoldenExample
from app.evaluation.runners.ci_runner import build_rag_metrics, make_deepeval_test_case
from app.rag.chains import build_phase_one_chain

pytestmark = pytest.mark.skipif(
    not get_settings().has_llm_judge_credentials,
    reason="Fully LLM-driven harness: set OPENAI_API_KEY to run this suite.",
)


@pytest.fixture(scope="module")
def rag_chain():
    return build_phase_one_chain()


@pytest.mark.parametrize("example", GOLDEN_DATASET, ids=lambda example: example.id)
def test_golden_rag_metrics(example: GoldenExample, rag_chain) -> None:
    """Assert all required RAG metrics with DeepEval's pytest integration."""

    result = rag_chain.invoke(example.query)
    test_case = make_deepeval_test_case(example, result)
    assert_test(test_case, metrics=[metric for _, metric in build_rag_metrics()])


def test_missing_key_fails_fast() -> None:
    """get_chat_model must raise a clear config error when no key is set."""

    from app.core.config import Settings
    from app.rag.chains import get_chat_model

    keyless = Settings(openai_api_key=None, _env_file=None)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        get_chat_model(keyless)
