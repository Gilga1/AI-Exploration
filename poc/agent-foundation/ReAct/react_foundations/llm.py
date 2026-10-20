"""LLM backends for live ReAct runs (OpenRouter chat by default)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from react_foundations.env_config import dotenv_hint, load_project_dotenv


class LLMClient(Protocol):
    def complete(self, prompt: str, stop: list[str] | None = None) -> str: ...


@dataclass
class ChatCompletionsLLM:
    """Chat-completions API (OpenRouter, OpenAI, vLLM, etc.) with a single user turn per call."""

    model: str
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    temperature: float = 0.0
    max_tokens: int = 256
    extra_headers: dict[str, str] = field(default_factory=dict)
    system_prompt: str | None = (
        "Follow the task format exactly. Emit only the continuation requested "
        "(Thought, Action, or answer text) with no preamble."
    )
    timeout: int = 120

    def complete(self, prompt: str, stop: list[str] | None = None) -> str:
        import requests

        messages: list[dict[str, str]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if stop:
            payload["stop"] = stop

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        response = requests.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        if stop:
            cut = len(text)
            for token in stop:
                idx = text.find(token)
                if idx != -1:
                    cut = min(cut, idx)
            text = text[:cut]
        return text


@dataclass
class OpenRouterLLM(ChatCompletionsLLM):
    """OpenRouter chat models."""

    base_url: str = "https://openrouter.ai/api/v1"

    @classmethod
    def from_env(cls) -> OpenRouterLLM:
        load_project_dotenv()
        api_key = os.environ.get("OPENROUTER_API_KEY")
        model = os.environ.get("OPENROUTER_MODEL")
        if not api_key:
            raise RuntimeError(dotenv_hint())
        if not model:
            raise RuntimeError(
                f"OPENROUTER_MODEL is not set.\n{dotenv_hint()}"
            )
        api_key = api_key.strip()
        model = model.strip()
        extra: dict[str, str] = {}
        referer = os.environ.get("OPENROUTER_HTTP_REFERER")
        if referer:
            extra["HTTP-Referer"] = referer
        title = os.environ.get("OPENROUTER_APP_NAME", "ai-exploration-react")
        extra["X-Title"] = title
        base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        temperature = float(os.environ.get("OPENROUTER_TEMPERATURE", "0"))
        max_tokens = int(os.environ.get("OPENROUTER_MAX_TOKENS", "256"))
        return cls(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_headers=extra,
        )


@dataclass
class OpenAICompatibleLLM:
    """Legacy text completions API (instruct models). Prefer OpenRouterLLM for OpenRouter."""

    model: str
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    temperature: float = 0.0
    max_tokens: int = 160

    def complete(self, prompt: str, stop: list[str] | None = None) -> str:
        import requests

        response = requests.post(
            f"{self.base_url.rstrip('/')}/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "prompt": prompt,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stop": stop or ["\n"],
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["text"]


def llm_from_env() -> LLMClient:
    """Construct a live LLM from environment variables (OpenRouter by default)."""
    load_project_dotenv()
    backend = os.environ.get("REACT_LLM_BACKEND", "openrouter").lower()
    if backend == "openrouter":
        return OpenRouterLLM.from_env()
    if backend == "openai_completions":
        key = os.environ.get("OPENAI_API_KEY")
        model = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo-instruct")
        if not key:
            raise RuntimeError("Set OPENAI_API_KEY for openai_completions backend.")
        return OpenAICompatibleLLM(model=model, api_key=key)
    raise ValueError(f"Unknown REACT_LLM_BACKEND: {backend}")
