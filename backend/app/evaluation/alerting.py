"""Threshold alerting on aggregated eval scores.

Runs opportunistically whenever /metrics endpoints are read (cheap: one query)
and posts to a Slack-compatible webhook when a metric drops below threshold.
State is kept per-process so the same regression is not re-alerted constantly;
production deployments can swap this for a scheduled job without changing the
public API.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import EvalResult
from app.db.session import session_scope

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS: dict[str, float] = {
    "Faithfulness": 0.7,
    "ContextualPrecision": 0.7,
    "ContextualRecall": 0.7,
    "ToolCorrectness": 0.8,
    "TaskCompletion": 0.8,
    "LoopEfficiency": 0.7,
}
_COOLDOWN = timedelta(minutes=30)
_last_alerted: dict[str, datetime] = {}


def _webhook_post(payload: dict[str, Any]) -> bool:
    """Deliver one alert to the configured webhook. Never raises, never blocks
    the caller for long (M2 fix): the request is bounded to 5s and runs with a
    short-lived client so a hanging webhook can't stall /metrics responses."""

    url = get_settings().alert_webhook_url
    if not url:
        return False
    try:
        response = httpx.post(url, json=payload, timeout=5.0)
        return response.status_code < 300
    except Exception:
        logger.warning("alert webhook delivery failed", exc_info=True)
        return False


def check_score_thresholds() -> list[dict[str, Any]]:
    """Return breached metrics and fire webhooks for new regressions."""

    thresholds = {**DEFAULT_THRESHOLDS, **_settings_thresholds()}
    breaches: list[dict[str, Any]] = []

    with session_scope() as session:
        rows = session.execute(
            select(EvalResult.metric_name, EvalResult.score).where(
                EvalResult.score.is_not(None)
            )
        ).all()

    sums: dict[str, list[float]] = {}
    for metric_name, score in rows:
        sums.setdefault(metric_name, []).append(score)

    now = datetime.now(timezone.utc)
    for metric_name, floor in thresholds.items():
        scores = sums.get(metric_name)
        if not scores:
            continue
        average = sum(scores) / len(scores)
        if average >= floor:
            continue

        breach = {
            "metric": metric_name,
            "avg_score": round(average, 4),
            "threshold": floor,
            "cases_scored": len(scores),
        }
        breaches.append(breach)

        last = _last_alerted.get(metric_name)
        if last is None or now - last > _COOLDOWN:
            delivered = _webhook_post(
                {
                    "text": (
                        f":rotating_light: Eval harness regression — {metric_name} "
                        f"averages {breach['avg_score']:.2f} "
                        f"(threshold {floor:.2f}) over {len(scores)} scored traces."
                    )
                }
            )
            breach["webhook_delivered"] = delivered
            _last_alerted[metric_name] = now

    return breaches


def _settings_thresholds() -> dict[str, float]:
    """Optional JSON overrides via APP_ALERT_THRESHOLDS='{"Faithfulness":0.8}'."""

    raw = get_settings().alert_thresholds_json
    if not raw:
        return {}
    try:
        import json

        parsed = json.loads(raw)
        return {str(k): float(v) for k, v in parsed.items()}
    except (ValueError, TypeError):
        logger.warning("ignoring malformed APP_ALERT_THRESHOLDS value")
        return {}
