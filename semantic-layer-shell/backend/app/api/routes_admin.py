from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.rbac import ROLE_SCOPES, Role, get_current_user, require_scope

router = APIRouter(prefix="/api/v1", tags=["admin"])


class RoleAssignRequest(BaseModel):
    user_id: str
    role: Role


@router.get("/audit/queries")
async def list_audit_queries(
    limit: int = 50, user: dict = Depends(require_scope("roles"))
) -> list[dict]:
    del user
    from app.audit.store import AuditStore

    return AuditStore().recent(limit=limit)


@router.get("/users/me")
async def get_me(user: dict = Depends(get_current_user)) -> dict:
    return {
        "id": user["id"],
        "role": user["role"].value,
        "scopes": sorted(ROLE_SCOPES[user["role"]]),
    }


@router.get("/roles")
async def list_roles(user: dict = Depends(require_scope("roles"))) -> dict:
    del user
    return {
        role.value: sorted(scopes) for role, scopes in ROLE_SCOPES.items()
    }


@router.post("/roles/assign")
async def assign_role(body: RoleAssignRequest, user: dict = Depends(require_scope("roles"))) -> dict:
    del user
    return {"user_id": body.user_id, "role": body.role.value, "status": "assigned"}
