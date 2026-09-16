"""Parse ReAct Thought / Action strings the way the original notebook does."""

from __future__ import annotations

import re
from dataclasses import dataclass

ACTION_RE = re.compile(
    r"^(?P<name>search|lookup|finish|think)\[(?P<arg>.*)\]$",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class ParsedAction:
    name: str
    argument: str

    def to_env(self) -> str:
        return f"{self.name}[{self.argument}]"


def parse_action(text: str) -> ParsedAction:
    """Parse `Search[entity]` / `lookup[keyword]` / `Finish[answer]`."""
    raw = text.strip()
    match = ACTION_RE.match(raw)
    if not match:
        raise ValueError(f"Invalid action: {text!r}")
    return ParsedAction(name=match.group("name").lower(), argument=match.group("arg"))


def canonicalize_action(text: str) -> str:
    """Official code lowercases only the first character: Search[...] -> search[...]."""
    stripped = text.strip()
    if not stripped:
        return stripped
    return stripped[0].lower() + stripped[1:]


def parse_thought_action(generated: str, step: int) -> tuple[str, str]:
    """Split a model continuation after `Thought {step}:`.

    Expected form::

        <thought>
        Action {step}: Search[entity]
    """
    text = generated.strip()
    marker = f"\nAction {step}:"
    if marker in text:
        thought, action = text.split(marker, 1)
        return thought.strip(), action.strip()
    prefix = f"Action {step}:"
    if text.startswith(prefix):
        return "", text[len(prefix) :].strip()
    first, _, rest = text.partition("\n")
    return first.strip(), rest.strip()
