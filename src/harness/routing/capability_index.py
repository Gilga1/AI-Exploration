from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal


@dataclass
class CapabilityEntry:
    name: str
    kind: Literal["skill", "agent"]
    description: str
    tags: list[str]
    text: str
    vector: dict[str, float]


@dataclass
class RetrievalCandidate:
    name: str
    kind: Literal["skill", "agent"]
    score: float
    description: str


class CapabilityIndex:
    """Lightweight bag-of-words index for tier-1 retrieval (no external embedder)."""

    def __init__(self) -> None:
        self._entries: list[CapabilityEntry] = []

    def add(self, name: str, kind: Literal["skill", "agent"], description: str, tags: list[str]) -> None:
        text = " ".join([name.replace("_", " "), description, *tags]).lower()
        self._entries.append(
            CapabilityEntry(
                name=name,
                kind=kind,
                description=description,
                tags=tags,
                text=text,
                vector=_vectorize(text),
            )
        )

    def search(self, query: str, *, k: int = 5) -> list[RetrievalCandidate]:
        query_vector = _vectorize(query.lower())
        scored = [
            RetrievalCandidate(
                name=entry.name,
                kind=entry.kind,
                score=_cosine(query_vector, entry.vector),
                description=entry.description,
            )
            for entry in self._entries
        ]
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:k]

    def __len__(self) -> int:
        return len(self._entries)


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _vectorize(text: str) -> dict[str, float]:
    tokens = _TOKEN_PATTERN.findall(text)
    counts: dict[str, float] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0.0) + 1.0
    norm = math.sqrt(sum(value * value for value in counts.values())) or 1.0
    return {token: value / norm for token, value in counts.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    return sum(a[token] * b[token] for token in shared)
