from unittest.mock import MagicMock, patch

import pytest

from react_foundations.llm import ChatCompletionsLLM, OpenRouterLLM, llm_from_env


def test_chat_completions_parses_response():
    llm = ChatCompletionsLLM(model="test/model", api_key="key")
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Thought 1: plan\nAction 1: Search[x]"}}],
    }
    with patch("requests.post", return_value=mock_response) as post:
        text = llm.complete("Question: foo\nThought 1:", stop=["\nObservation"])
    assert text.startswith("Thought 1:")
    post.assert_called_once()
    body = post.call_args.kwargs["json"]
    assert body["model"] == "test/model"
    assert body["messages"][-1]["content"].startswith("Question:")


def test_openrouter_from_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct")
    llm = OpenRouterLLM.from_env()
    assert llm.model == "meta-llama/llama-3.1-8b-instruct"
    assert llm.api_key == "or-key"
    assert llm.extra_headers["X-Title"] == "ai-exploration-react"


def test_llm_from_env_openrouter(monkeypatch):
    monkeypatch.setenv("REACT_LLM_BACKEND", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    assert isinstance(llm_from_env(), OpenRouterLLM)


def test_openrouter_from_env_missing_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_MODEL", "x")
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        OpenRouterLLM.from_env()
