"""Optional API-key auth for production deployments (P6-T3).

Disabled entirely unless APP_API_KEY is configured — local/dev stays friction-free.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency: 401s when APP_API_KEY is set and not supplied."""

    expected = get_settings().api_key
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header",
        )
