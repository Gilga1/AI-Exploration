from __future__ import annotations

from pathlib import Path

import yaml

from harness.agents.declarative import DeclarativeAgent
from harness.agents.profile_models import AgentProfile, AgentProfileOverrides, merge_profile_manifest, validate_profile_overrides
from harness.config.models import ConfigPlane
from harness.config.secrets import resolve_tree
from harness.core.errors import BootstrapValidationError
from harness.registry.registry import ToolRegistry


class AgentProfileRegistry:
    def __init__(self, profiles: list[AgentProfile] | None = None) -> None:
        self._profiles = {profile.name: profile for profile in profiles or []}

    @property
    def profiles(self) -> list[AgentProfile]:
        return list(self._profiles.values())

    def get(self, name: str) -> AgentProfile | None:
        return self._profiles.get(name)

    def list_summaries(self, tool_registry: ToolRegistry) -> list[dict]:
        summaries: list[dict] = []
        for profile in self._profiles.values():
            base = tool_registry.agents.get(profile.base_agent)
            summaries.append(
                {
                    "name": profile.name,
                    "base_agent": profile.base_agent,
                    "description": profile.description,
                    "capability_tags": profile.capability_tags,
                    "overrides": profile.overrides.model_dump(exclude_none=True),
                    "base_agent_exists": base is not None,
                }
            )
        return summaries


def load_agent_profiles(
    config_root: str | Path,
    *,
    config: ConfigPlane,
    registry: ToolRegistry,
    telemetry: object | None = None,
    approval_store: object | None = None,
    force_stub_models: bool = False,
    checkpointer: object | None = None,
    connectors: dict[str, object] | None = None,
) -> AgentProfileRegistry:
    profiles_dir = Path(config_root) / "agent_profiles"
    if not profiles_dir.is_dir():
        return AgentProfileRegistry()

    profiles: list[AgentProfile] = []
    errors: list[str] = []

    for yaml_file in sorted(profiles_dir.glob("*.yaml")):
        data = resolve_tree(yaml.safe_load(yaml_file.read_text()) or {})
        if not data:
            continue
        profile = _parse_profile(data)
        profiles.append(profile)

        if profile.name in registry.agents:
            errors.append(f"Profile {profile.name!r} collides with existing agent name")
            continue

        base_agent = registry.agents.get(profile.base_agent)
        if base_agent is None:
            errors.append(
                f"Profile {profile.name!r} references unknown base agent {profile.base_agent!r}"
            )
            continue

        errors.extend(validate_profile_overrides(profile, base_agent.manifest))
        merged_manifest = merge_profile_manifest(profile, base_agent.manifest)
        agent = DeclarativeAgent(
            manifest=merged_manifest,
            config=config,
            registry=registry,
            telemetry=telemetry,
            approval_store=approval_store,
            force_stub_models=force_stub_models,
            checkpointer=checkpointer,
            connectors=connectors or {},
        )
        registry.register_agent(agent)

    if errors:
        raise BootstrapValidationError(errors)

    return AgentProfileRegistry(profiles)


def _parse_profile(data: dict) -> AgentProfile:
    overrides_raw = data.get("overrides") or {}
    overrides = AgentProfileOverrides(**overrides_raw) if isinstance(overrides_raw, dict) else AgentProfileOverrides()
    payload = {key: value for key, value in data.items() if key != "overrides"}
    payload["overrides"] = overrides
    return AgentProfile(**payload)
