from __future__ import annotations

from app.config.settings import get_settings


class GraphNotAvailableError(RuntimeError):
    """Raised when Neo4j is required but unavailable and registry fallback is disabled."""


def registry_fallback_allowed() -> bool:
    settings = get_settings()
    return settings.allow_registry_fallback or settings.debug


def require_graph_or_fallback(context: str) -> None:
    if not registry_fallback_allowed():
        raise GraphNotAvailableError(
            f"{context}: Neo4j graph is required. "
            "Publish a graph version or set ALLOW_REGISTRY_FALLBACK=true for local dev."
        )
