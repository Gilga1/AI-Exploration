from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from harness.core.models import AgentManifest


class AgentProfileOverrides(BaseModel):
    max_steps: int | None = None
    max_tokens_budget: int | None = None
    timeout_s: int | None = None
    system_prompt_fragment: str | None = None
    allowed_tools: list[str] | None = None
    config: dict[str, Any] | None = None


class AgentProfile(BaseModel):
    name: str
    base_agent: str
    description: str = ""
    capability_tags: list[str] = Field(default_factory=list)
    overrides: AgentProfileOverrides = Field(default_factory=AgentProfileOverrides)


ALLOWED_OVERRIDE_FIELDS = frozenset(AgentProfileOverrides.model_fields.keys())


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def validate_profile_overrides(profile: AgentProfile, base_manifest: AgentManifest) -> list[str]:
    errors: list[str] = []
    overrides = profile.overrides

    if overrides.allowed_tools is not None:
        base_tools = set(base_manifest.allowed_tools)
        extra = set(overrides.allowed_tools) - base_tools
        if extra:
            errors.append(
                f"Profile {profile.name!r} cannot add tools outside base agent "
                f"{profile.base_agent!r}: {sorted(extra)}"
            )

    if overrides.max_steps is not None and overrides.max_steps <= 0:
        errors.append(f"Profile {profile.name!r} max_steps must be positive")

    return errors


def merge_profile_manifest(profile: AgentProfile, base_manifest: AgentManifest) -> AgentManifest:
    overrides = profile.overrides
    data = base_manifest.model_dump()
    data["name"] = profile.name
    data["description"] = profile.description or base_manifest.description
    data["profile_of"] = base_manifest.name

    if profile.capability_tags:
        data["capability_tags"] = list(
            dict.fromkeys([*base_manifest.capability_tags, *profile.capability_tags])
        )

    if overrides.max_steps is not None:
        data["max_steps"] = overrides.max_steps
    if overrides.max_tokens_budget is not None:
        data["max_tokens_budget"] = overrides.max_tokens_budget
    if overrides.timeout_s is not None:
        data["timeout_s"] = overrides.timeout_s
    if overrides.allowed_tools is not None:
        data["allowed_tools"] = list(overrides.allowed_tools)
    if overrides.config:
        data["config"] = deep_merge(base_manifest.config, overrides.config)
    if overrides.system_prompt_fragment:
        data["system_prompt"] = (
            f"{base_manifest.system_prompt.rstrip()}\n\n{overrides.system_prompt_fragment.strip()}"
        )

    return AgentManifest(**data)
