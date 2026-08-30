from __future__ import annotations

import json
from typing import Any, AsyncIterator

from app.agents.nodes import QueryPipeline
from app.config.settings import get_settings


async def stream_query_events(question: str, metric_id: str | None = None) -> AsyncIterator[str]:
    pipeline = QueryPipeline()
    async for event in pipeline.run(question=question, metric_id=metric_id):
        yield json.dumps(event) + "\n"


def format_ndjson_event(event: dict[str, Any]) -> str:
    return json.dumps(event) + "\n"
