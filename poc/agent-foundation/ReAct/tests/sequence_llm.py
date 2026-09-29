"""Test-only LLM that returns a fixed list of completions (not used in notebook or CLI)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SequenceLLM:
    completions: list[str]
    calls: list[str] = field(default_factory=list)

    def complete(self, prompt: str, stop: list[str] | None = None) -> str:
        self.calls.append(prompt)
        if not self.completions:
            raise RuntimeError("SequenceLLM has no remaining completions")
        text = self.completions.pop(0)
        if stop:
            cut = len(text)
            for token in stop:
                idx = text.find(token)
                if idx != -1:
                    cut = min(cut, idx)
            text = text[:cut]
        return text
