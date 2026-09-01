"""Optional API-key auth for production deployments."""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency: 401 when auth is required and the key is missing/invalid."""

    settings = get_settings()
    if not settings.auth_required:
        return

    expected = settings.api_key
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is required but APP_API_KEY is not configured.",
        )
    if not secrets.compare_digest(x_api_key or "", expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header",
        )
