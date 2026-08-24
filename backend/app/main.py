"""FastAPI entrypoint for the Agentic RAG Evaluation Harness."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.agent_routes import router as agent_router
from app.api.v1.eval_routes import router as eval_router
from app.api.v1.metrics_routes import router as metrics_router
from app.api.v1.trace_routes import router as trace_router
from app.core.config import get_settings
from app.core.telemetry import configure_telemetry
from app.db.session import init_db

settings = get_settings()
configure_telemetry(settings)

app = FastAPI(title=settings.app_name)
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


@app.on_event("startup")
def initialise_trace_store() -> None:
    """Create the local SQLite tables (or configured Postgres tables) for dev."""

    init_db()


@app.get("/health")
async def health() -> dict[str, str]:
    """Return a lightweight process health signal."""

    return {"status": "ok"}
