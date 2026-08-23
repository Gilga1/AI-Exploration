from __future__ import annotations

from harness.config.models import ConfigPlane
from harness.routing.capability_index import CapabilityIndex, RetrievalCandidate
from harness.routing.decision import RoutingDecision
from harness.settings import HarnessSettings
from harness.telemetry.bus import TelemetryBus
from harness.telemetry.events import RoutingDecisionEvent


class TieredRouter:
    def __init__(
        self,
        index: CapabilityIndex,
        settings: HarnessSettings,
        telemetry: TelemetryBus,
        config: ConfigPlane | None = None,
    ) -> None:
        self._index = index
        self._settings = settings
        self._telemetry = telemetry
        self._config = config

    def route(self, message: str, *, trace_id: str, parent_span_id: str | None = None) -> RoutingDecision:
        candidates = self._index.search(message, k=self._settings.routing_top_k)
        if not candidates:
            decision = RoutingDecision(
                selected="direct",
                kind="direct",
                confidence=1.0,
                rationale="No routable capabilities registered",
                candidates=[],
            )
            self._emit(trace_id, decision, parent_span_id)
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
            self._emit(trace_id, decision, parent_span_id)
            return decision

        if self._settings.routing_use_llm and self._config is not None:
            from harness.llm.router import LLMRouter

            decision = LLMRouter(self._config).disambiguate(message, candidates, trace_id=trace_id)
            self._emit(trace_id, decision, parent_span_id)
            return decision

        decision = RoutingDecision(
            selected=top.name,
            kind=top.kind,
            confidence=top.score,
            rationale=f"Ambiguous routing; defaulting to top candidate {top.name!r}",
            candidates=candidates,
        )
        self._emit(trace_id, decision, parent_span_id)
        return decision

    def _emit(self, trace_id: str, decision: RoutingDecision, parent_span_id: str | None = None) -> None:
        self._telemetry.emit(
            RoutingDecisionEvent(
                trace_id=trace_id,
                span_id=self._telemetry.new_span_id(),
                parent_span_id=parent_span_id,
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
