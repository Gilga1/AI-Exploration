"""LLM backends. Scripted completions make the loop testable without API keys."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, prompt: str, stop: list[str] | None = None) -> str: ...


@dataclass
class ScriptedLLM:
    """Return pre-recorded continuations in order (paper trajectory replays)."""

    completions: list[str]
    calls: list[str] = field(default_factory=list)

    def complete(self, prompt: str, stop: list[str] | None = None) -> str:
        self.calls.append(prompt)
        if not self.completions:
            raise RuntimeError("ScriptedLLM has no remaining completions")
        text = self.completions.pop(0)
        if stop:
            cut = len(text)
            for token in stop:
                idx = text.find(token)
                if idx != -1:
                    cut = min(cut, idx)
            text = text[:cut]
        return text


@dataclass
class OpenAICompatibleLLM:
    """Optional chat/completions backend. Not required for the notebook tests."""

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
