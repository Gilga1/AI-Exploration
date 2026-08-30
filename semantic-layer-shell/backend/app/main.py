from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_admin import router as admin_router
from app.api.routes_graph import router as graph_router
from app.api.routes_query import router as query_router
from app.api.routes_registry import load_bundled_registry, router as registry_router
from app.bootstrap import bootstrap_registry, ensure_graph_schema
from app.config.settings import get_settings
from app.graph.neo4j_client import get_neo4j_client
from app.llm.client import LLMClient
from app.warehouse.snowflake_client import SnowflakeClient

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    load_bundled_registry()

    if ensure_graph_schema():
        version_id = bootstrap_registry()
        if version_id:
            logger.info("Bootstrapped graph version: %s", version_id)

    llm = LLMClient()
    if llm.enabled:
        logger.info("LLM enabled (model=%s)", settings.openai_model)
    else:
        logger.warning("OPENAI_API_KEY not set — using heuristic decompose/reason/answer")

    sf = SnowflakeClient()
    if sf.is_configured:
        if sf.connect():
            logger.info("Snowflake connected")
        else:
            logger.warning("Snowflake configured but connection failed: %s", sf.last_error)
    else:
        logger.warning("Snowflake env vars not set — execute stage will return empty rows")

    yield

    get_neo4j_client().close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(registry_router)
    app.include_router(graph_router)
    app.include_router(query_router)
    app.include_router(admin_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/graph")
    async def health_graph() -> dict:
        client = get_neo4j_client()
        connected = client.connect()
        body: dict = {
            "status": "ok" if connected else "degraded",
            "neo4j_connected": connected,
        }
        if not connected and client.last_error:
            body["error"] = client.last_error
        if connected:
            rows = client.run(
                "MATCH (v:GraphVersion) RETURN v.id AS id ORDER BY v.created_at DESC LIMIT 1"
            )
            if rows:
                body["last_graph_version_id"] = rows[0].get("id")
        return body

    @app.get("/health/warehouse")
    async def health_warehouse() -> dict:
        sf = SnowflakeClient()
        configured = sf.is_configured
        connected = sf.connect() if configured else False
        body: dict = {
            "status": "ok" if connected else ("not_configured" if not configured else "degraded"),
            "snowflake_configured": configured,
            "snowflake_connected": connected,
        }
        if sf.last_error:
            body["error"] = sf.last_error
        return body

    @app.get("/health/llm")
    async def health_llm() -> dict:
        llm = LLMClient()
        return {
            "status": "ok" if llm.enabled else "not_configured",
            "llm_enabled": llm.enabled,
            "model": settings.openai_model if llm.enabled else None,
        }

    return app


app = create_app()
