"""Small, dependency-free helpers for the GenAI span attributes used in Phase 2."""

from __future__ import annotations

import json
from typing import Any, Iterable

GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_USAGE_PROMPT_TOKENS = "gen_ai.usage.prompt_tokens"
GEN_AI_USAGE_COMPLETION_TOKENS = "gen_ai.usage.completion_tokens"
GEN_AI_INPUT = "gen_ai.input"
GEN_AI_OUTPUT = "gen_ai.output"
GEN_AI_RETRIEVAL_DOCUMENT_IDS = "gen_ai.retrieval.document_ids"
GEN_AI_RETRIEVAL_DOCUMENT_SCORES = "gen_ai.retrieval.document_scores"

_MAX_ATTRIBUTE_LENGTH = 16_000


def attribute_value(value: Any) -> str | bool | int | float | list[str] | list[bool] | list[int] | list[float]:
    """Convert rich LangChain values into a safe OpenTelemetry attribute value."""

    if value is None:
        return ""
    if isinstance(value, (str, bool, int, float)):
        return value[:_MAX_ATTRIBUTE_LENGTH] if isinstance(value, str) else value
    if isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
        return [item[:_MAX_ATTRIBUTE_LENGTH] for item in value]
    if isinstance(value, (list, tuple)) and all(isinstance(item, bool) for item in value):
        return list(value)
    if isinstance(value, (list, tuple)) and all(isinstance(item, int) for item in value):
        return list(value)
    if isinstance(value, (list, tuple)) and all(isinstance(item, (int, float)) for item in value):
        return [float(item) for item in value]
    try:
        encoded = json.dumps(value, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        encoded = str(value)
    return encoded[:_MAX_ATTRIBUTE_LENGTH]


def input_attributes(value: Any) -> dict[str, Any]:
    """Return the normalized GenAI input attribute."""

    return {GEN_AI_INPUT: attribute_value(value)}


def output_attributes(value: Any) -> dict[str, Any]:
    """Return the normalized GenAI output attribute."""

    return {GEN_AI_OUTPUT: attribute_value(value)}


def model_attributes(serialized: dict[str, Any] | None, provider: str | None = None) -> dict[str, Any]:
    """Extract provider/model fields from common LangChain callback payloads."""

    serialized = serialized or {}
    kwargs = serialized.get("kwargs") or {}
    model = (
        kwargs.get("model")
        or kwargs.get("model_name")
        or serialized.get("model")
        or serialized.get("name")
        or "unknown"
    )
    system = provider or serialized.get("provider") or serialized.get("id") or "langchain"
    if isinstance(system, (list, tuple)):
        system = system[-1] if system else "langchain"
    return {
        GEN_AI_SYSTEM: attribute_value(system),
        GEN_AI_REQUEST_MODEL: attribute_value(model),
    }


def usage_attributes(response: Any) -> dict[str, int]:
    """Extract prompt/completion counts from common LangChain response shapes."""

    candidates: list[dict[str, Any]] = []
    if isinstance(response, dict):
        candidates.extend(
            candidate
            for candidate in (response, response.get("llm_output"), response.get("usage_metadata"))
            if isinstance(candidate, dict)
        )
    else:
        for value in (getattr(response, "llm_output", None), getattr(response, "usage_metadata", None)):
            if isinstance(value, dict):
                candidates.append(value)
        generations = getattr(response, "generations", None)
        if generations and generations[0]:
            generation = generations[0][0]
            metadata = getattr(getattr(generation, "message", None), "usage_metadata", None)
            if isinstance(metadata, dict):
                candidates.append(metadata)

    aliases = {
        GEN_AI_USAGE_PROMPT_TOKENS: ("prompt_tokens", "input_tokens"),
        GEN_AI_USAGE_COMPLETION_TOKENS: ("completion_tokens", "output_tokens"),
    }
    attributes: dict[str, int] = {}
    for attribute, keys in aliases.items():
        for candidate in candidates:
            token_usage = candidate.get("token_usage", candidate)
            if not isinstance(token_usage, dict):
                continue
            value = next((token_usage[key] for key in keys if key in token_usage), None)
            if value is not None:
                try:
                    attributes[attribute] = int(value)
                except (TypeError, ValueError):
                    pass
                break
    return attributes


def retrieval_attributes(documents: Iterable[Any]) -> dict[str, Any]:
    """Extract document ids and optional similarity scores from retriever output."""

    document_ids: list[str] = []
    scores: list[float] = []
    for index, document in enumerate(documents):
        metadata = getattr(document, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = document.get("metadata", {}) if isinstance(document, dict) else {}
        document_ids.append(str(metadata.get("id", metadata.get("source", index))))
        score = metadata.get("score", metadata.get("similarity_score"))
        if score is not None:
            try:
                scores.append(float(score))
            except (TypeError, ValueError):
                pass

    attributes: dict[str, Any] = {GEN_AI_RETRIEVAL_DOCUMENT_IDS: document_ids}
    if scores:
        attributes[GEN_AI_RETRIEVAL_DOCUMENT_SCORES] = scores
    return attributes
