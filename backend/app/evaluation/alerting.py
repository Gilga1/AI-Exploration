"""Threshold alerting on aggregated eval scores."""

from __future__ import annotations

import ipaddress
import logging
import socket
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.models import AlertCooldown, EvalResult
from app.db.session import init_db, session_scope

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS: dict[str, float] = {
    "Faithfulness": 0.7,
    "ContextualPrecision": 0.7,
    "ContextualRecall": 0.7,
    "ToolCorrectness": 0.8,
    "TaskCompletion": 0.8,
    "LoopEfficiency": 0.7,
}


def validate_webhook_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        raise ValueError("Alert webhook URL must use http or https.")
    if not parsed.hostname:
        raise ValueError("Alert webhook URL must include a hostname.")
    if get_settings().environment not in ("development", "dev", "local", "test"):
        if parsed.scheme != "https":
            raise ValueError("Alert webhook URL must use https outside development.")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    except socket.gaierror as exc:
        raise ValueError(f"Alert webhook hostname could not be resolved: {parsed.hostname}") from exc
    for family, _, _, _, sockaddr in addresses:
        if family not in {socket.AF_INET, socket.AF_INET6}:
            continue
        host = sockaddr[0]
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("Alert webhook URL must not target private or local addresses.")


def _webhook_post(payload: dict[str, Any]) -> bool:
    url = get_settings().alert_webhook_url
    if not url:
        return False
    try:
        response = httpx.post(url, json=payload, timeout=5.0)
        return response.status_code < 300
    except Exception:
        logger.warning("alert webhook delivery failed", exc_info=True)
        return False


def _settings_thresholds() -> dict[str, float]:
    raw = get_settings().alert_thresholds_json
    if not raw:
        return {}
    try:
        import json

        parsed = json.loads(raw)
        return {str(key): float(value) for key, value in parsed.items()}
    except (ValueError, TypeError):
        logger.warning("ignoring malformed APP_ALERT_THRESHOLDS value")
        return {}


def _cooldown_expired(session, metric_name: str, now: datetime, cooldown: timedelta) -> bool:
    init_db()
    record = session.get(AlertCooldown, metric_name)
    if record is None:
        return True
    return now - record.alerted_at > cooldown


def _mark_alerted(session, metric_name: str, now: datetime) -> None:
    record = session.get(AlertCooldown, metric_name)
    if record is None:
        session.add(AlertCooldown(metric_name=metric_name, alerted_at=now))
    else:
        record.alerted_at = now


def check_score_thresholds() -> list[dict[str, Any]]:
    settings = get_settings()
    thresholds = {**DEFAULT_THRESHOLDS, **_settings_thresholds()}
    breaches: list[dict[str, Any]] = []
    window_start = datetime.now(timezone.utc) - timedelta(hours=settings.alert_window_hours)
    cooldown = timedelta(minutes=settings.alert_cooldown_minutes)

    with session_scope() as session:
        rows = session.execute(
            select(EvalResult.metric_name, EvalResult.score)
            .where(EvalResult.score.is_not(None))
            .where(EvalResult.created_at >= window_start)
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
                "window_hours": settings.alert_window_hours,
            }
            breaches.append(breach)

            if _cooldown_expired(session, metric_name, now, cooldown):
                delivered = _webhook_post(
                    {
                        "text": (
                            f":rotating_light: Eval harness regression — {metric_name} "
                            f"averages {breach['avg_score']:.2f} "
                            f"(threshold {floor:.2f}) over {len(scores)} scored traces "
                            f"in the last {settings.alert_window_hours}h."
                        )
                    }
                )
                breach["webhook_delivered"] = delivered
                _mark_alerted(session, metric_name, now)

    return breaches
