from __future__ import annotations

import pytest
from pydantic import BaseModel

from harness.bootstrap import bootstrap, validate_registry
from harness.core.errors import RegistryCollisionError, UnresolvedDependencyError
from harness.core.models import ExecutionMode, SkillManifest, ToolSpec
from harness.core.protocols import BaseSkill
from harness.core.context import RunContext
from harness.registry import ToolRegistry, register_tool
from harness.registry.decorators import bind_registries
from harness.registry.data_sources import DataSourceRegistry
from harness.settings import HarnessSettings


class InModel(BaseModel):
    value: str


class OutModel(BaseModel):
    value: str


class _TestTool:
    spec = ToolSpec(
        name="test_tool",
        description="test",
        input_schema=InModel,
        output_schema=OutModel,
    )

    async def run(self, args: InModel, *, context: RunContext) -> OutModel:
        return OutModel(value=args.value.upper())


class _DependentSkill(BaseSkill):
    manifest = SkillManifest(
        name="dependent_skill",
        description="needs test_tool",
        required_tools=["test_tool"],
        input_schema=InModel,
        output_schema=OutModel,
    )

    async def execute(self, payload: InModel, *, context: RunContext) -> OutModel:
        return OutModel(value=payload.value)


@pytest.mark.asyncio
async def test_bootstrap_discovers_echo_tool():
    settings = HarnessSettings(scan_paths=["harness/tools"])
    registry, connectors, imported = await bootstrap(settings)
    assert "echo" in registry.tools
    assert len(imported) >= 1
    assert connectors.connectors == {}


@pytest.mark.asyncio
async def test_admin_capabilities_payload():
    settings = HarnessSettings(scan_paths=["harness/tools"])
    registry, connectors, _ = await bootstrap(settings)
    payload = registry.introspection_payload(connectors)
    assert payload["counts"]["tools"] == 1
    assert payload["tools"][0]["name"] == "echo"


def test_registry_collision():
    registry = ToolRegistry()
    registry.register_tool(_TestTool())
    with pytest.raises(RegistryCollisionError):
        registry.register_tool(_TestTool())


def test_skill_missing_tool_dependency():
    registry = ToolRegistry()
    with pytest.raises(UnresolvedDependencyError):
        registry.register_skill(_DependentSkill())


def test_skill_registers_after_tool():
    registry = ToolRegistry()
    registry.register_tool(_TestTool())
    registry.register_skill(_DependentSkill())
    assert "dependent_skill" in registry.skills


@pytest.mark.asyncio
async def test_echo_tool_run():
    settings = HarnessSettings(scan_paths=["harness/tools"])
    registry, _, _ = await bootstrap(settings)
    tool = registry.tools["echo"]
    result = await tool.run(
        tool.spec.input_schema(message="hello"),
        context=RunContext(trace_id="test"),
    )
    assert result.message == "hello"
    assert result.length == 5
