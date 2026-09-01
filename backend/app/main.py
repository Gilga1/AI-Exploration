"""FastAPI entrypoint for the Agentic RAG Evaluation Harness."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.agent_routes import router as agent_router
from app.api.v1.eval_routes import router as eval_router
from app.api.v1.metrics_routes import router as metrics_router
from app.api.v1.trace_routes import router as trace_router
from app.core.config import get_settings, validate_startup_settings
from app.core.llm import configure_llm_environment
from app.core.telemetry import configure_telemetry
from app.db.session import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    validate_startup_settings(settings)
    configure_llm_environment(settings)
    configure_telemetry(settings)
    init_db()
    yield


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url="/docs" if settings.expose_openapi else None,
    redoc_url="/redoc" if settings.expose_openapi else None,
    openapi_url=settings.open_api_url if settings.expose_openapi else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(eval_router, prefix="/api/v1")
app.include_router(trace_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")
app.include_router(agent_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
