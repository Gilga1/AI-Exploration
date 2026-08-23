from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from harness.bootstrap import bootstrap
from harness.registry.data_sources import DataSourceRegistry
from harness.registry.registry import ToolRegistry
from harness.settings import HarnessSettings

_state: dict = {}


def get_tool_registry() -> ToolRegistry:
    registry = _state.get("tool_registry")
    if registry is None:
        raise RuntimeError("Harness not bootstrapped")
    return registry


def get_connector_registry() -> DataSourceRegistry:
    registry = _state.get("connector_registry")
    if registry is None:
        raise RuntimeError("Harness not bootstrapped")
    return registry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: HarnessSettings = app.state.settings
    tool_registry, connector_registry, imported = await bootstrap(settings)
    _state["tool_registry"] = tool_registry
    _state["connector_registry"] = connector_registry
    _state["imported_modules"] = imported
    yield
    _state.clear()


def create_app(settings: HarnessSettings | None = None) -> FastAPI:
    settings = settings or HarnessSettings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.settings = settings

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "app": settings.app_name}

    @app.get("/admin/capabilities")
    async def admin_capabilities() -> dict:
        tool_registry = get_tool_registry()
        connector_registry = get_connector_registry()
        payload = tool_registry.introspection_payload(connector_registry)
        payload["imported_modules"] = _state.get("imported_modules", [])
        return payload

    return app
