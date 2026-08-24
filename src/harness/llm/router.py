from __future__ import annotations

import json
import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage

from harness.config.models import ConfigPlane
from harness.llm.factory import build_chat_model
from harness.routing.capability_index import RetrievalCandidate
from harness.routing.decision import RoutingDecision


class LLMRouter:
    """LLM-based disambiguation when retrieval margin is ambiguous."""

    def __init__(self, config: ConfigPlane, router_model: str = "fast_router") -> None:
        self._config = config
        self._router_model = router_model

    def disambiguate(
        self,
        message: str,
        candidates: list[RetrievalCandidate],
        *,
        trace_id: str,
    ) -> RoutingDecision:
        model_cfg = next(
            (m for m in self._config.models.models if m.name == self._router_model),
            None,
        )
        if model_cfg is None or model_cfg.provider == "stub":
            return _keyword_fallback(message, candidates)

        model = build_chat_model(model_cfg)
        options = "\n".join(
            f"- {c.name} ({c.kind}): {c.description} [score={c.score:.2f}]"
            for c in candidates
        )
        prompt = (
            "Pick the best capability for the user request.\n"
            "Respond with JSON only: "
            '{"name": "<capability_name>", "kind": "skill|agent|direct", "rationale": "..."}\n\n'
            f"User request: {message}\n\nCandidates:\n{options}"
        )
        response = model.invoke(
            [
                SystemMessage(content="You are a routing classifier for an agent harness."),
                HumanMessage(content=prompt),
            ]
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        parsed = _parse_json(content)
        name = parsed.get("name", candidates[0].name)
        kind = parsed.get("kind", candidates[0].kind)
        if kind not in ("skill", "agent", "direct"):
            kind = candidates[0].kind
        matched = next((c for c in candidates if c.name == name), candidates[0])
        return RoutingDecision(
            selected=matched.name,
            kind=kind if kind != "direct" else matched.kind,  # type: ignore[arg-type]
            confidence=matched.score,
            rationale=parsed.get("rationale", f"LLM selected {matched.name!r}"),
            candidates=candidates,
            used_llm=True,
        )


def _keyword_fallback(message: str, candidates: list[RetrievalCandidate]) -> RoutingDecision:
    message_lower = message.lower()
    for candidate in candidates:
        if candidate.name.replace("_", " ") in message_lower:
            return RoutingDecision(
                selected=candidate.name,
                kind=candidate.kind,
                confidence=candidate.score,
                rationale=f"Keyword matched {candidate.name!r}",
                candidates=candidates,
                used_llm=True,
            )
    top = candidates[0]
    return RoutingDecision(
        selected=top.name,
        kind=top.kind,
        confidence=top.score,
        rationale="LLM router unavailable; defaulted to top retrieval score",
        candidates=candidates,
        used_llm=True,
    )


def _parse_json(content: str) -> dict:
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
