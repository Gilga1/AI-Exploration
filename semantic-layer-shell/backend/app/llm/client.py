from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class DecomposeResult(BaseModel):
    intent: str = "metric_query"
    search_terms: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    time_range: str | None = None


class ReasonResult(BaseModel):
    metric_id: str
    parameters: dict[str, str] = Field(default_factory=dict)
    dimensions: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    rationale: str = ""


class LLMClient:
    """OpenAI-backed LLM for decompose / reason / answer stages.

    Falls back to heuristics when OPENAI_API_KEY is not configured.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Any = None

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

    def decompose(self, question: str) -> dict[str, Any]:
        if not self.enabled:
            return self._decompose_heuristic(question)

        try:
            result = self._chat_json(
                system=(
                    "You decompose natural-language data questions into structured intent. "
                    "Return JSON with keys: intent, search_terms (list of strings for semantic search), "
                    "entities (business nouns), time_range (optional string or null)."
                ),
                user=f"Question: {question}",
                model_cls=DecomposeResult,
            )
            return {
                "intent": result.intent,
                "search_terms": result.search_terms or [question],
                "entities": result.entities,
                "time_range": result.time_range,
                "raw_question": question,
                "llm": True,
            }
        except Exception as exc:
            logger.warning("LLM decompose failed, using heuristic: %s", exc)
            return self._decompose_heuristic(question)

    def reason(
        self,
        question: str,
        candidates: list[dict[str, Any]],
        metric_id: str | None = None,
    ) -> dict[str, Any]:
        if metric_id:
            return {"metric_id": metric_id, "parameters": {}, "dimensions": [], "llm": False}

        if not self.enabled or not candidates:
            return self._reason_heuristic(candidates)

        candidate_lines = "\n".join(
            f"- id={c['id']} kind={c.get('kind')} name={c.get('name')} description={c.get('description', '')[:120]}"
            for c in candidates[:15]
        )
        try:
            result = self._chat_json(
                system=(
                    "You select the best metric/measure for a user question from an enumerated candidate list. "
                    "You MUST pick metric_id from the provided ids only — never invent one. "
                    "Return JSON: metric_id, parameters (dict of param->value), dimensions (list), "
                    "confidence (0-1), rationale (short string). Prefer kind=metric when available."
                ),
                user=f"Question: {question}\n\nCandidates:\n{candidate_lines}",
                model_cls=ReasonResult,
            )
            valid_ids = {c["id"] for c in candidates}
            if result.metric_id not in valid_ids:
                logger.warning("LLM picked invalid metric %s, falling back", result.metric_id)
                return self._reason_heuristic(candidates)
            return {
                "metric_id": result.metric_id,
                "parameters": result.parameters,
                "dimensions": result.dimensions,
                "confidence": result.confidence,
                "rationale": result.rationale,
                "llm": True,
            }
        except Exception as exc:
            logger.warning("LLM reason failed, using heuristic: %s", exc)
            return self._reason_heuristic(candidates)

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
    def _decompose_heuristic(question: str) -> dict[str, Any]:
        terms = [t.strip("?.,!") for t in question.lower().split() if len(t) > 3]
        return {
            "intent": "metric_query",
            "search_terms": terms or [question],
            "entities": [],
            "time_range": None,
            "raw_question": question,
            "llm": False,
        }

    @staticmethod
    def _reason_heuristic(candidates: list[dict[str, Any]]) -> dict[str, Any]:
        metrics = [c for c in candidates if c.get("kind") == "metric"]
        if metrics:
            top = metrics[0]
            return {"metric_id": top["id"], "parameters": {}, "dimensions": [], "llm": False}
        if candidates:
            return {"metric_id": candidates[0]["id"], "parameters": {}, "dimensions": [], "llm": False}
        return {"metric_id": "net_flow_ratio", "parameters": {}, "dimensions": [], "llm": False}

    @staticmethod
    def _answer_heuristic(metric_id: str, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return f"No rows returned for metric {metric_id}."
        return f"Query for {metric_id} returned {len(rows)} row(s)."
