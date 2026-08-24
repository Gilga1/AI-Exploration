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

    if _cross_domain_request(message):
        return True

    if candidates and len(candidates) >= 2:
        top = candidates[0]
        second = candidates[1]
        if top.kind == "agent" and second.kind == "agent" and second.score >= 0.15:
            if top.name != second.name and _cross_domain_request(message):
                return True

    return False


def _cross_domain_request(message: str) -> bool:
    """Multi-agent when the request spans distinct capability domains."""
    lowered = message.lower()
    research_domain = any(
        keyword in lowered for keyword in ("competitor", "research", "positioning", "brief")
    )
    analytics_domain = any(
        keyword in lowered
        for keyword in ("advisor", "sales", "analyze", "analysis", "aum", "product", "chart")
    )
    return research_domain and analytics_domain
