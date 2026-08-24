from __future__ import annotations

from typing import TYPE_CHECKING

from harness.core.errors import RegistryCollisionError, UnresolvedDependencyError
from harness.core.models import CapabilitySummary
from harness.core.protocols import BaseAgent, BaseSkill, BaseTool

if TYPE_CHECKING:
    from harness.registry.data_sources import DataSourceRegistry


def _schema_json(model_type: type) -> dict:
    if hasattr(model_type, "model_json_schema"):
        return model_type.model_json_schema()
    return {}


class ToolRegistry:
    """Capability plane: tools, skills, and agents."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._skills: dict[str, BaseSkill] = {}
        self._agents: dict[str, BaseAgent] = {}
        self._capability_index: object | None = None

    @property
    def tools(self) -> dict[str, BaseTool]:
        return dict(self._tools)

    @property
    def skills(self) -> dict[str, BaseSkill]:
        return dict(self._skills)

    @property
    def agents(self) -> dict[str, BaseAgent]:
        return dict(self._agents)

    def register_tool(self, tool: BaseTool) -> None:
        if tool.spec.name in self._tools:
            raise RegistryCollisionError(tool.spec.name)
        self._tools[tool.spec.name] = tool

    def register_skill(self, skill: BaseSkill) -> None:
        if skill.manifest.name in self._skills:
            raise RegistryCollisionError(skill.manifest.name)
        missing = set(skill.manifest.required_tools) - self._tools.keys()
        if missing:
            raise UnresolvedDependencyError(skill.manifest.name, missing)
        self._skills[skill.manifest.name] = skill

    def register_agent(self, agent: BaseAgent) -> None:
        if agent.manifest.name in self._agents:
            raise RegistryCollisionError(agent.manifest.name)
        self._agents[agent.manifest.name] = agent

    async def build_capability_index(self, embedder: object | None = None) -> None:
        """Embed agent/skill descriptions for routing (Phase 4)."""
        self._capability_index = {"embedder": embedder, "entries": self.list_capabilities()}

    def list_capabilities(self) -> list[CapabilitySummary]:
        summaries: list[CapabilitySummary] = []
        for tool in self._tools.values():
            summaries.append(
                CapabilitySummary(
                    kind="tool",
                    name=tool.spec.name,
                    description=tool.spec.description,
                    capability_tags=tool.spec.capability_tags,
                    input_schema=_schema_json(tool.spec.input_schema),
                    output_schema=_schema_json(tool.spec.output_schema),
                    metadata={
                        "side_effects": tool.spec.side_effects,
                        "requires_approval": tool.spec.requires_approval,
                        "execution_mode": tool.spec.execution_mode.value,
                    },
                )
            )
        for skill in self._skills.values():
            summaries.append(
                CapabilitySummary(
                    kind="skill",
                    name=skill.manifest.name,
                    description=skill.manifest.description,
                    capability_tags=skill.manifest.capability_tags,
                    input_schema=_schema_json(skill.manifest.input_schema),
                    output_schema=_schema_json(skill.manifest.output_schema),
                    metadata={"required_tools": skill.manifest.required_tools},
                )
            )
        for agent in self._agents.values():
            summaries.append(
                CapabilitySummary(
                    kind="agent",
                    name=agent.manifest.name,
                    description=agent.manifest.description,
                    capability_tags=agent.manifest.capability_tags,
                    metadata={
                        "allowed_tools": agent.manifest.allowed_tools,
                        "allowed_skills": agent.manifest.allowed_skills,
                        "model_config_ref": agent.manifest.model_config_ref,
                    },
                )
            )
        return summaries

    def introspection_payload(self, connectors: DataSourceRegistry | None = None) -> dict:
        payload: dict = {
            "tools": [c.model_dump() for c in self.list_capabilities() if c.kind == "tool"],
            "skills": [c.model_dump() for c in self.list_capabilities() if c.kind == "skill"],
            "agents": [c.model_dump() for c in self.list_capabilities() if c.kind == "agent"],
            "counts": {
                "tools": len(self._tools),
                "skills": len(self._skills),
                "agents": len(self._agents),
            },
        }
        if connectors is not None:
            payload["connectors"] = connectors.list_summaries()
            payload["counts"]["connectors"] = len(connectors.connectors)
        return payload
