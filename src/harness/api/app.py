from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

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

    @app.post("/v1/handle", response_model=OrchestratorResult)
    async def handle_request(request: IncomingRequest) -> OrchestratorResult:
        state = get_bootstrap_state()
        return await state.orchestrator.handle(request)

    @app.post("/v1/resume", response_model=OrchestratorResult)
    async def resume_request(request: ResumeRequest) -> OrchestratorResult:
        state = get_bootstrap_state()
        return await state.orchestrator.resume(request)

    return app
