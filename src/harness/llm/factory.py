from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from harness.config.models import ModelEndpointConfig


def build_chat_model(cfg: ModelEndpointConfig) -> BaseChatModel:
    if cfg.provider == "stub":
        return FakeListChatModel(responses=["Stub model response."])

    if cfg.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if not cfg.api_key:
            raise ValueError(
                f"Model {cfg.name!r} requires HARNESS_SECRET_ANTHROPIC_API_KEY "
                "(or api_key in models.yaml)"
            )
        return ChatAnthropic(
            model=cfg.model,
            api_key=cfg.api_key,
            max_tokens=cfg.max_tokens,
        )

    if cfg.provider == "openai":
        from langchain_openai import ChatOpenAI

        if not cfg.api_key:
            raise ValueError(
                f"Model {cfg.name!r} requires HARNESS_SECRET_OPENAI_API_KEY "
                "(or api_key in models.yaml)"
            )
        return ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            max_tokens=cfg.max_tokens,
        )

    raise ValueError(f"Unsupported model provider: {cfg.provider!r}")
