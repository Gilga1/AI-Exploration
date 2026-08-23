from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from harness.routing.capability_index import CapabilityIndex, RetrievalCandidate
from harness.settings import HarnessSettings
from harness.telemetry.bus import TelemetryBus
from harness.telemetry.events import RoutingDecisionEvent


@dataclass
class RoutingDecision:
    selected: str
    kind: Literal["skill", "agent", "direct"]
    confidence: float
    rationale: str
    candidates: list[RetrievalCandidate]
    used_llm: bool = False


class TieredRouter:
    def __init__(self, index: CapabilityIndex, settings: HarnessSettings, telemetry: TelemetryBus) -> None:
        self._index = index
        self._settings = settings
        self._telemetry = telemetry

    def route(self, message: str, *, trace_id: str) -> RoutingDecision:
        candidates = self._index.search(message, k=self._settings.routing_top_k)
        if not candidates:
            decision = RoutingDecision(
                selected="direct",
                kind="direct",
                confidence=1.0,
                rationale="No routable capabilities registered",
                candidates=[],
            )
            self._emit(trace_id, decision)
            return decision

        top = candidates[0]
        second_score = candidates[1].score if len(candidates) > 1 else 0.0
        margin = top.score - second_score

        if margin >= self._settings.routing_clear_margin and top.score >= self._settings.routing_min_score:
            rationale = (
                f"Clear top-1 match for {top.kind} {top.name!r} "
                f"(score={top.score:.2f}, margin={margin:.2f})"
            )
            decision = RoutingDecision(
                selected=top.name,
                kind=top.kind,
                confidence=top.score,
                rationale=rationale,
                candidates=candidates,
            )
            self._emit(trace_id, decision)
            return decision

        if self._settings.routing_use_llm:
            decision = self._llm_disambiguate(message, candidates, trace_id)
            self._emit(trace_id, decision)
            return decision

        decision = RoutingDecision(
            selected=top.name,
            kind=top.kind,
            confidence=top.score,
            rationale=f"Ambiguous routing; defaulting to top candidate {top.name!r}",
            candidates=candidates,
        )
        self._emit(trace_id, decision)
        return decision

    def _llm_disambiguate(
        self,
        message: str,
        candidates: list[RetrievalCandidate],
        trace_id: str,
    ) -> RoutingDecision:
        # Phase 4 stub: keyword heuristic until model router is wired in Phase 5+.
        message_lower = message.lower()
        for candidate in candidates:
            if candidate.name.replace("_", " ") in message_lower:
                return RoutingDecision(
                    selected=candidate.name,
                    kind=candidate.kind,
                    confidence=candidate.score,
                    rationale=f"LLM stub matched keyword for {candidate.name!r}",
                    candidates=candidates,
                    used_llm=True,
                )
        top = candidates[0]
        return RoutingDecision(
            selected=top.name,
            kind=top.kind,
            confidence=top.score,
            rationale="LLM stub defaulted to highest retrieval score",
            candidates=candidates,
            used_llm=True,
        )

    def _emit(self, trace_id: str, decision: RoutingDecision) -> None:
        self._telemetry.emit(
            RoutingDecisionEvent(
                trace_id=trace_id,
                span_id=self._telemetry.new_span_id(),
                candidates=[
                    {"name": c.name, "kind": c.kind, "score": c.score} for c in decision.candidates
                ],
                selected=decision.selected,
                selected_kind=decision.kind,
                rationale=decision.rationale,
                confidence=decision.confidence,
                used_llm=decision.used_llm,
            )
        )
