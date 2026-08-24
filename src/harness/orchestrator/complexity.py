from __future__ import annotations

from harness.core.request import IncomingRequest
from harness.routing.capability_index import RetrievalCandidate
from harness.settings import HarnessSettings


def should_use_multi_agent(
    message: str,
    settings: HarnessSettings,
    *,
    request: IncomingRequest | None = None,
    candidates: list[RetrievalCandidate] | None = None,
) -> bool:
    mode = settings.orchestration_mode
    if request and request.orchestration.mode != "auto":
        mode = request.orchestration.mode

    if mode == "single":
        return False
    if mode == "multi":
        return True

    return _ambiguous_multi_capability_match(settings, candidates)


def _ambiguous_multi_capability_match(
    settings: HarnessSettings,
    candidates: list[RetrievalCandidate] | None,
) -> bool:
    """Use multi-agent planning when routing is ambiguous across capabilities."""
    if not candidates or len(candidates) < 2:
        return False

    synthesizer = settings.orchestration_synthesizer_agent
    viable = [
        candidate
        for candidate in candidates
        if candidate.name != synthesizer and candidate.score >= settings.routing_min_score
    ]
    if len(viable) < 2:
        return False

    top = viable[0]
    second = viable[1]
    if top.name == second.name:
        return False

    margin = top.score - second.score
    return margin < settings.routing_clear_margin
