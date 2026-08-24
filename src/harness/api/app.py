from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from harness.bootstrap import BootstrapState, bootstrap
from harness.core.request import IncomingRequest, OrchestratorResult, ResumeRequest
from harness.settings import HarnessSettings

_state: BootstrapState | None = None


def get_bootstrap_state() -> BootstrapState:
    if _state is None:
        raise RuntimeError("Harness not bootstrapped")
    return _state


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _state
    from dotenv import load_dotenv

    load_dotenv()
    settings: HarnessSettings = app.state.settings
    _state = await bootstrap(settings)
    yield
    if _state is not None:
        _state.telemetry.flush_otel()
    _state = None


def create_app(settings: HarnessSettings | None = None) -> FastAPI:
    settings = settings or HarnessSettings.load()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.settings = settings

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "app": settings.app_name}

    @app.get("/admin/capabilities")
    async def admin_capabilities() -> dict:
        state = get_bootstrap_state()
        payload = state.tool_registry.introspection_payload(state.connector_registry)
        payload["imported_modules"] = state.imported_modules
        payload["config"] = {
            "context_packs": [pack.name for pack in state.config.context_packs],
            "models": [model.name for model in state.config.models.models],
            "mcp_servers": [server.name for server in state.config.mcp.servers if server.enabled],
            "connectors": [connector.name for connector in state.config.connectors],
        }
        payload["routing_index_size"] = len(state.capability_index)
        payload["langfuse_enabled"] = state.telemetry.langfuse_enabled
        return payload

    @app.get("/admin/events")
    async def admin_events(trace_id: str | None = None, limit: int = 100) -> dict:
        state = get_bootstrap_state()
        if trace_id:
            events = state.telemetry.list_events_for_trace(trace_id)
        else:
            ledger = state.telemetry.ledger
            events = ledger.list_recent(limit) if ledger is not None else state.telemetry.list_events()
        return {"events": events, "count": len(events)}

    @app.get("/admin/approvals")
    async def admin_approvals(limit: int = 50) -> dict:
        state = get_bootstrap_state()
        pending = state.approval_store.list_pending(limit=limit)
        return {"pending": pending, "count": len(pending)}

    @app.get("/admin/plans")
    async def admin_plans(limit: int = 50, status: str | None = None) -> dict:
        state = get_bootstrap_state()
        records = state.plan_store.list_recent(limit=limit, status=status)
        return {
            "plans": [
                {
                    "plan_id": record.plan_id,
                    "trace_id": record.trace_id,
                    "thread_id": record.thread_id,
                    "status": record.status,
                    "message": record.message,
                    "metrics": record.metrics,
                    "updated_at": record.updated_at.isoformat(),
                }
                for record in records
            ],
            "count": len(records),
        }

    @app.get("/admin/plans/{plan_id}")
    async def admin_plan_detail(plan_id: str) -> dict:
        state = get_bootstrap_state()
        record = state.plan_store.get(plan_id)
        if record is None:
            return {"error": f"Plan {plan_id!r} not found"}
        return {
            "plan_id": record.plan_id,
            "trace_id": record.trace_id,
            "thread_id": record.thread_id,
            "status": record.status,
            "message": record.message,
            "plan": record.plan,
            "task_results": record.task_results,
            "metrics": record.metrics,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
        }

    @app.get("/admin/plans/{plan_id}/waterfall")
    async def admin_plan_waterfall(plan_id: str) -> dict:
        state = get_bootstrap_state()
        record = state.plan_store.get(plan_id)
        if record is None:
            return {"error": f"Plan {plan_id!r} not found"}
        from harness.orchestrator.waterfall import build_waterfall

        events = state.telemetry.list_events_for_trace(record.trace_id)
        return {
            "plan_id": plan_id,
            "trace_id": record.trace_id,
            "waterfall": build_waterfall(events),
            "events": events,
        }

    @app.get("/admin/agent_profiles")
    async def admin_agent_profiles() -> dict:
        state = get_bootstrap_state()
        profiles = state.profile_registry.list_summaries(state.tool_registry)
        return {"profiles": profiles, "count": len(profiles)}

    @app.get("/admin/workflows")
    async def admin_workflows() -> dict:
        state = get_bootstrap_state()
        workflows = state.workflow_registry.list_summaries()
        return {
            "workflows": workflows,
            "count": len(workflows),
            "planner_mode": state.settings.orchestration_planner,
            "match_threshold": state.settings.orchestration_workflow_match_threshold,
        }

    @app.get("/admin/metrics")
    async def admin_metrics() -> dict:
        state = get_bootstrap_state()
        return {
            "plans": state.plan_store.metrics_summary(),
            "routing_index_size": len(state.capability_index),
            "registry": state.tool_registry.introspection_payload(state.connector_registry)["counts"],
        }

    @app.post("/v1/handle", response_model=OrchestratorResult)
    async def handle_request(request: IncomingRequest) -> OrchestratorResult:
        state = get_bootstrap_state()
        return await state.orchestrator.handle(request)

    @app.post("/v1/resume", response_model=OrchestratorResult)
    async def resume_request(request: ResumeRequest) -> OrchestratorResult:
        state = get_bootstrap_state()
        return await state.orchestrator.resume(request)

    @app.get("/v1/runs/{trace_id}/events")
    async def stream_run_events(trace_id: str) -> StreamingResponse:
        state = get_bootstrap_state()

        async def event_generator() -> AsyncIterator[str]:
            seen = 0
            idle_ticks = 0
            while idle_ticks < 20:
                events = state.telemetry.list_events_for_trace(trace_id)
                if len(events) > seen:
                    for event in events[seen:]:
                        yield f"data: {json.dumps(event)}\n\n"
                    seen = len(events)
                    idle_ticks = 0
                else:
                    idle_ticks += 1
                await asyncio.sleep(0.5)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    return app
