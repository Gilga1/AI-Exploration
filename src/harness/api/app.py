from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from harness.bootstrap import BootstrapState, bootstrap
from harness.core.request import IncomingRequest, OrchestratorResult
from harness.settings import HarnessSettings

_state: BootstrapState | None = None


def get_bootstrap_state() -> BootstrapState:
    if _state is None:
        raise RuntimeError("Harness not bootstrapped")
    return _state


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _state
    settings: HarnessSettings = app.state.settings
    _state = await bootstrap(settings)
    yield
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
        return payload

    @app.post("/v1/handle", response_model=OrchestratorResult)
    async def handle_request(request: IncomingRequest) -> OrchestratorResult:
        state = get_bootstrap_state()
        return await state.orchestrator.handle(request)

    return app
