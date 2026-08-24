from __future__ import annotations

from typing import Any

from harness.registry.registry import ToolRegistry


def infer_skill_input(
    skill_name: str,
    message: str,
    registry: ToolRegistry | None = None,
) -> dict[str, Any]:
    if registry is not None and skill_name in registry.skills:
        return registry.skills[skill_name].infer_input(message)
    return {"message": message}
