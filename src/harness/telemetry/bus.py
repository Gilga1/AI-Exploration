from __future__ import annotations

import uuid
from typing import Any

from harness.telemetry.events import TraceEventBase


class TelemetryBus:
    def __init__(self) -> None:
        self._events: list[TraceEventBase] = []

    def emit(self, event: TraceEventBase) -> None:
        self._events.append(event)

    def list_events(self) -> list[dict[str, Any]]:
        return [event.model_dump(mode="json") for event in self._events]

    def new_span_id(self) -> str:
        return uuid.uuid4().hex[:16]
