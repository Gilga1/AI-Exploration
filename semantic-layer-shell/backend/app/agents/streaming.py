from __future__ import annotations

import json
from typing import Any, AsyncIterator

from app.agents.nodes import QueryPipeline


async def stream_query_events(
    question: str,
    metric_id: str | None = None,
    revision_hint: str | None = None,
    disambiguation: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    pipeline = QueryPipeline()
    async for event in pipeline.run(
        question=question,
        metric_id=metric_id,
        revision_hint=revision_hint,
        disambiguation=disambiguation,
    ):
        yield json.dumps(event) + "\n"


def format_ndjson_event(event: dict[str, Any]) -> str:
    return json.dumps(event) + "\n"
