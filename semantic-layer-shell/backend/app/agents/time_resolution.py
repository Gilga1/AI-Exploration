from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def resolve_time_range(
    time_range: dict[str, Any] | str | None,
    *,
    reference_date: date | None = None,
) -> dict[str, Any] | None:
    if not time_range:
        return None

    today = reference_date or date.today()
    text = time_range
    range_type = "relative"
    if isinstance(time_range, dict):
        text = time_range.get("text") or time_range.get("relative") or ""
        range_type = time_range.get("type", "relative")

    if not text:
        return None

    normalized = str(text).strip().lower()
    start: date | None = None
    end: date | None = today

    if normalized in {"today"}:
        start = today
    elif normalized in {"yesterday"}:
        start = today - timedelta(days=1)
        end = today - timedelta(days=1)
    elif normalized.startswith("last ") and "week" in normalized:
        weeks = _extract_number(normalized, default=1)
        start = today - timedelta(days=7 * weeks)
    elif normalized.startswith("last ") and "day" in normalized:
        days = _extract_number(normalized, default=1)
        start = today - timedelta(days=days)
    elif normalized.startswith("last ") and "month" in normalized:
        months = _extract_number(normalized, default=1)
        start = today - timedelta(days=30 * months)
    else:
        return {
            "text": str(text),
            "type": range_type,
            "start": None,
            "end": None,
            "predicate": None,
            "unresolved": True,
        }

    return {
        "text": str(text),
        "type": range_type,
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "predicate": (
            f"BETWEEN '{start.isoformat()}' AND '{end.isoformat()}'"
            if start and end
            else None
        ),
    }


def time_predicate_for_measure(
    resolved_time: dict[str, Any] | None,
    measure: dict[str, Any],
) -> str | None:
    if not resolved_time or not resolved_time.get("start") or not resolved_time.get("end"):
        return None

    time_filter = measure.get("time_filter") or {}
    if isinstance(time_filter, str):
        import json

        try:
            time_filter = json.loads(time_filter)
        except json.JSONDecodeError:
            time_filter = {}

    column = time_filter.get("column")
    alias = time_filter.get("alias")
    if not column:
        return None

    qualified = f"{alias}.{column}" if alias else column
    return f"{qualified} BETWEEN '{resolved_time['start']}' AND '{resolved_time['end']}'"


def _extract_number(text: str, default: int = 1) -> int:
    for token in text.split():
        if token.isdigit():
            return int(token)
    return default
