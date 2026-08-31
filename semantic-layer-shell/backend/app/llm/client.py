from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.agents.dimension_selection import (
    get_metric_dimensions,
    infer_dimensions_from_intent,
    validate_and_filter_dimensions,
)
from app.graph.entity_catalog import format_catalog_for_prompt
from app.config.settings import get_settings
from app.graph.resolver import GraphResolver

logger = logging.getLogger(__name__)


class MentionResult(BaseModel):
    text: str
    entity_type: str | None = None
    role: str = "filter"
    subtype: str | None = None
    confidence: float = 0.0


class TimeRangeResult(BaseModel):
    text: str
    type: str = "relative"


class DecomposeResult(BaseModel):
    intent: str = "metric_query"
    search_terms: list[str] = Field(default_factory=list)
    mentions: list[MentionResult] = Field(default_factory=list)
    time_range: TimeRangeResult | str | None = None


class ReasonResult(BaseModel):
    metric_id: str
    parameters: dict[str, str] = Field(default_factory=dict)
    dimensions: list[str] = Field(default_factory=list)
    mention_bindings: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    rationale: str = ""


class LLMClient:
    """OpenAI-backed LLM for decompose / reason / answer stages.

    Falls back to heuristics when OPENAI_API_KEY is not configured.
    """

    def __init__(self, resolver: GraphResolver | None = None) -> None:
        self.settings = get_settings()
        self._client: Any = None
        self.resolver = resolver

    @property
    def enabled(self) -> bool:
        return bool(self.settings.openai_api_key)

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            kwargs: dict[str, Any] = {"api_key": self.settings.openai_api_key}
            if self.settings.openai_base_url:
                kwargs["base_url"] = self.settings.openai_base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def _chat_json(self, system: str, user: str, model_cls: type[BaseModel]) -> BaseModel:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        return model_cls.model_validate(data)

    def decompose(
        self, question: str, entity_catalog: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        entity_catalog = entity_catalog or []
        if not self.enabled:
            return self._decompose_heuristic(question, entity_catalog)

        catalog_text = format_catalog_for_prompt(entity_catalog)
        try:
            result = self._chat_json(
                system=(
                    "You decompose natural-language data questions into structured intent. "
                    "Return JSON with keys: intent, search_terms (list), mentions (list of objects with "
                    "text, entity_type, role, subtype, confidence), time_range (object with text and type or null). "
                    "entity_type MUST be one of the provided entity catalog ids. "
                    "role is filter or dimension. Extract time phrases like 'last 2 weeks' into time_range."
                ),
                user=f"Question: {question}\n\nEntity catalog:\n{catalog_text}",
                model_cls=DecomposeResult,
            )
            mentions = [m.model_dump() for m in result.mentions]
            time_range = result.time_range
            if isinstance(time_range, TimeRangeResult):
                time_range = time_range.model_dump()
            elif isinstance(time_range, str):
                time_range = {"text": time_range, "type": "relative"}
            return {
                "intent": result.intent,
                "search_terms": result.search_terms or [question],
                "mentions": mentions,
                "entities": [m["text"] for m in mentions],
                "time_range": time_range,
                "raw_question": question,
                "llm": True,
            }
        except Exception as exc:
            logger.warning("LLM decompose failed, using heuristic: %s", exc)
            return self._decompose_heuristic(question, entity_catalog)

    def reason(
        self,
        question: str,
        candidates: list[dict[str, Any]],
        metric_id: str | None = None,
        intent: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if metric_id:
            selection = {
                "metric_id": metric_id,
                "parameters": {},
                "dimensions": [],
                "confidence": 1.0,
                "rationale": "Metric confirmed by caller.",
                "llm": False,
                "confirmed": True,
            }
            return validate_and_filter_dimensions(selection, metric_id, self.resolver)

        if not self.enabled or not candidates:
            intent = dict(intent or {})
            intent.setdefault("raw_question", question)
            intent.setdefault("search_terms", [question])
            selection = self._reason_heuristic(question, candidates, intent)
        else:
            selection = self._reason_with_llm(question, candidates, intent or {})

        return validate_and_filter_dimensions(
            selection, selection["metric_id"], self.resolver
        )

    def _reason_with_llm(
        self,
        question: str,
        candidates: list[dict[str, Any]],
        intent: dict[str, Any],
    ) -> dict[str, Any]:
        candidate_lines = "\n".join(
            self._format_candidate(c) for c in candidates[:15]
        )
        try:
            result = self._chat_json(
                system=(
                    "You select the best metric/measure for a user question from an enumerated candidate list. "
                    "You MUST pick metric_id from the provided ids only — never invent one. "
                    "For dimensions, you MUST only choose from each metric's allowed_dimensions list when "
                    "the user asks for a breakdown (e.g. by fund, by share class). "
                    "Return JSON: metric_id, parameters, dimensions, mention_bindings (list), "
                    "confidence (0-1), rationale. Prefer kind=metric when available."
                ),
                user=(
                    f"Question: {question}\n"
                    f"Mentions from decompose: {intent.get('mentions', [])}\n\n"
                    f"Candidates:\n{candidate_lines}"
                ),
                model_cls=ReasonResult,
            )
            valid_ids = {c["id"] for c in candidates}
            if result.metric_id not in valid_ids:
                logger.warning("LLM picked invalid metric %s, falling back", result.metric_id)
                return self._reason_heuristic(question, candidates, intent)
            return {
                "metric_id": result.metric_id,
                "parameters": result.parameters,
                "dimensions": result.dimensions,
                "mention_bindings": result.mention_bindings,
                "confidence": result.confidence,
                "rationale": result.rationale,
                "llm": True,
            }
        except Exception as exc:
            logger.warning("LLM reason failed, using heuristic: %s", exc)
            return self._reason_heuristic(question, candidates, intent)

    @staticmethod
    def _format_candidate(candidate: dict[str, Any]) -> str:
        dims = candidate.get("dimensions") or []
        dim_text = f" allowed_dimensions={dims}" if dims else ""
        return (
            f"- id={candidate['id']} kind={candidate.get('kind')} name={candidate.get('name')} "
            f"description={str(candidate.get('description', ''))[:120]}{dim_text}"
        )

    def answer(
        self,
        question: str,
        metric_id: str,
        rows: list[dict[str, Any]],
        columns: list[str],
        sql: str | None = None,
    ) -> str:
        if not self.enabled:
            return self._answer_heuristic(metric_id, rows)

        preview = json.dumps(rows[:5], default=str)
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.settings.openai_model,
                temperature=0.3,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You summarize query results for a business user in 2-4 sentences. "
                            "Be factual — only describe what is in the data preview. "
                            "Do not invent numbers not shown."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Question: {question}\nMetric: {metric_id}\n"
                            f"Columns: {columns}\nRows (preview): {preview}\n"
                            f"Total rows: {len(rows)}"
                        ),
                    },
                ],
            )
            return response.choices[0].message.content or self._answer_heuristic(metric_id, rows)
        except Exception as exc:
            logger.warning("LLM answer failed, using heuristic: %s", exc)
            return self._answer_heuristic(metric_id, rows)

    @staticmethod
    def _decompose_heuristic(
        question: str, entity_catalog: list[dict[str, Any]]
    ) -> dict[str, Any]:
        terms = [t.strip("?.,!") for t in question.lower().split() if len(t) > 3]
        mentions: list[dict[str, Any]] = []
        q_lower = question.lower()
        for entity in entity_catalog:
            candidates = [entity.get("name", "")] + (entity.get("synonyms") or [])
            for attr in entity.get("attributes") or []:
                for value in attr.get("values") or []:
                    if str(value).lower() in q_lower:
                        mentions.append(
                            {
                                "text": str(value),
                                "entity_type": entity["id"],
                                "role": "filter",
                                "subtype": str(value),
                                "confidence": 0.7,
                            }
                        )
            for label in candidates:
                if label and label.lower() in q_lower:
                    mentions.append(
                        {
                            "text": label,
                            "entity_type": entity["id"],
                            "role": "filter",
                            "confidence": 0.6,
                        }
                    )

        time_range = None
        if "last" in q_lower and "week" in q_lower:
            time_range = {"text": "last 2 weeks", "type": "relative"}

        return {
            "intent": "metric_query",
            "search_terms": terms or [question],
            "mentions": mentions,
            "entities": [m["text"] for m in mentions],
            "time_range": time_range,
            "raw_question": question,
            "llm": False,
        }

    def _reason_heuristic(
        self,
        question: str,
        candidates: list[dict[str, Any]],
        intent: dict[str, Any],
    ) -> dict[str, Any]:
        metrics = [c for c in candidates if c.get("kind") == "metric"]
        pool = metrics or candidates
        if not pool:
            raise ValueError(
                "No metric candidates found. Publish the registry to Neo4j and ensure "
                "discovery returns results, or set ALLOW_REGISTRY_FALLBACK=true for local dev."
            )

        top = pool[0]
        second_score = pool[1].get("score", 0.0) if len(pool) > 1 else 0.0
        top_score = float(top.get("score", 0.85))
        gap = max(0.0, top_score - float(second_score))
        confidence = min(0.95, 0.55 + gap)

        allowed = top.get("dimensions") or get_metric_dimensions(top["id"], self.resolver)
        dimensions = infer_dimensions_from_intent(intent, allowed)

        return {
            "metric_id": top["id"],
            "parameters": {},
            "dimensions": dimensions,
            "mention_bindings": [
                {"mention_index": i, "entity_type": m.get("entity_type"), "apply_as": "filter"}
                for i, m in enumerate(intent.get("mentions") or [])
                if m.get("entity_type")
            ],
            "confidence": confidence,
            "rationale": "Heuristic top discovery candidate.",
            "llm": False,
        }

    @staticmethod
    def _answer_heuristic(metric_id: str, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return f"No rows returned for metric {metric_id}."
        return f"Query for {metric_id} returned {len(rows)} row(s)."
