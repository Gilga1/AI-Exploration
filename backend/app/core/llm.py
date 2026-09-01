"""Shared LLM client configuration for LangChain and DeepEval."""

from __future__ import annotations

import os
from typing import Any, Protocol

from app.core.config import Settings


class ChatModel(Protocol):
    provider_name: str

    def invoke(self, prompt: str) -> Any: ...


class LangChainChatModel:
    """Adapter exposing a stable provider label to the harness."""

    def __init__(self, inner: Any, *, provider_name: str) -> None:
        self._inner = inner
        self.provider_name = provider_name

    def invoke(self, prompt: str) -> Any:
        return self._inner.invoke(prompt)


def configure_llm_environment(settings: Settings) -> None:
    """Align DeepEval and other OpenAI-compatible clients with configured routing."""

    os.environ.setdefault("OPENAI_API_KEY", settings.llm_api_key)
    os.environ.setdefault("OPENAI_BASE_URL", settings.llm_base_url)


def get_chat_model(settings: Settings) -> ChatModel:
    """Return the configured OpenAI-compatible chat model (OpenRouter by default)."""

    if not settings.llm_api_key:
        raise RuntimeError(
            "LLM API key is not configured. Set OPENROUTER_API_KEY or APP_LLM_API_KEY."
        )

    configure_llm_environment(settings)

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError(
            "LLM API key is configured but langchain-openai is missing. "
            "Install the 'openai' optional dependency: pip install -e '.[openai]'"
        ) from exc

    return LangChainChatModel(
        ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
        ),
        provider_name=settings.llm_provider,
    )
