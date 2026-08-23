from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from harness.routing.capability_index import RetrievalCandidate


@dataclass
class RoutingDecision:
    selected: str
    kind: Literal["skill", "agent", "direct"]
    confidence: float
    rationale: str
    candidates: list[RetrievalCandidate]
    used_llm: bool = False
