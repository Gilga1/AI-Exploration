from __future__ import annotations

from typing import Any

import httpx

from harness.settings import HarnessSettings


async def maybe_send_plan_alert(
    *,
    settings: HarnessSettings,
    status: str,
    trace_id: str,
    plan_id: str,
    message: str,
    task_results: dict[str, Any] | None = None,
) -> None:
    webhook = settings.orchestration_alert_webhook_url
    if not webhook:
        return
    if status not in settings.orchestration_alert_on_statuses:
        return

    payload = {
        "event": "plan_run_finished",
        "status": status,
        "trace_id": trace_id,
        "plan_id": plan_id,
        "message": message,
        "task_results": task_results or {},
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(webhook, json=payload)
    except Exception:
        return
