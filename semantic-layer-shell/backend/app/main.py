from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_admin import router as admin_router
from app.api.routes_graph import router as graph_router
from app.api.routes_query import router as query_router
from app.api.routes_registry import load_bundled_registry, router as registry_router
from app.config.settings import get_settings
from app.graph.neo4j_client import get_neo4j_client
from app.graph.schema import CONSTRAINTS_AND_INDEXES
from app.warehouse.snowflake_client import SnowflakeClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_bundled_registry()
    client = get_neo4j_client()
    if client.connect():
        for stmt in CONSTRAINTS_AND_INDEXES:
            try:
                client.run(stmt)
            except Exception:
                pass
    yield
    client.close()


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
        return {"status": "ok" if connected else "degraded", "neo4j_connected": connected}

    @app.get("/health/warehouse")
    async def health_warehouse() -> dict:
        sf = SnowflakeClient()
        connected = sf.connect()
        return {"status": "ok" if connected else "degraded", "snowflake_connected": connected}

    return app


app = create_app()
