from __future__ import annotations

from enum import Enum
from typing import Callable

from fastapi import Depends, HTTPException, Request, status


class Role(str, Enum):
    VIEWER = "viewer"
    DEVELOPER = "developer"
    ADMIN = "admin"


ROLE_SCOPES: dict[Role, set[str]] = {
    Role.VIEWER: {
        "query",
        "graph.read",
        "health",
    },
    Role.DEVELOPER: {
        "query",
        "graph.read",
        "graph.write",
        "registry",
        "sql.preview",
        "health",
    },
    Role.ADMIN: {
        "query",
        "graph.read",
        "graph.write",
        "registry",
        "registry.rollback",
        "sql.preview",
        "roles",
        "health",
    },
}


def get_current_user(request: Request) -> dict:
    # Phase 1: header-based role for pilot; replace with real auth later
    role_header = request.headers.get("X-User-Role", "developer").lower()
    try:
        role = Role(role_header)
    except ValueError:
        role = Role.DEVELOPER
    return {"id": request.headers.get("X-User-Id", "pilot-user"), "role": role}


def require_scope(scope: str) -> Callable:
    def dependency(user: dict = Depends(get_current_user)) -> dict:
        role: Role = user["role"]
        if scope not in ROLE_SCOPES[role]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing scope: {scope}")
        return user

    return dependency
