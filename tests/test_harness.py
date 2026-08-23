from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from harness.api import create_app
from harness.bootstrap import bootstrap
from harness.config import load_config_plane, resolve_value
from harness.core.context import RunContext
from harness.core.errors import RegistryCollisionError, UnresolvedDependencyError
from harness.core.models import ExecutionMode, SkillManifest, ToolSpec
from harness.core.protocols import BaseSkill
from harness.core.request import IncomingRequest
from harness.registry import ToolRegistry
from harness.routing.capability_index import CapabilityIndex
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
    settings = HarnessSettings(scan_paths=["harness/tools"], connector_health_check=False)
    state = await bootstrap(settings)
    assert "echo" in state.tool_registry.tools
    assert len(state.imported_modules) >= 1


@pytest.mark.asyncio
async def test_bootstrap_loads_yaml_agents():
    settings = HarnessSettings(
        scan_paths=["harness/tools"],
        connector_health_check=False,
    )
    state = await bootstrap(settings)
    assert "competitor_research" in state.tool_registry.agents


@pytest.mark.asyncio
async def test_config_plane_loads_yaml():
    config = load_config_plane("harness")
    assert any(pack.name == "sales_glossary" for pack in config.context_packs)
    assert any(model.name == "primary_reasoner" for model in config.models.models)
    assert any(conn.name == "local_cache" for conn in config.connectors)


def test_secret_resolution():
    import os

    os.environ["HARNESS_SECRET_TEST_KEY"] = "resolved"
    assert resolve_value("${secret:test-key}") == "resolved"


@pytest.mark.asyncio
async def test_capability_index_ranks_markdown_skill():
    settings = HarnessSettings(
        scan_paths=["harness/tools", "harness/skills"],
        connector_health_check=False,
    )
    state = await bootstrap(settings)
    candidates = state.capability_index.search(
        "Turn my meeting notes into a PDF document", k=3
    )
    assert candidates
    assert candidates[0].name == "markdown_to_pdf"


@pytest.mark.asyncio
async def test_capability_index_ranks_competitor_agent():
    settings = HarnessSettings(
        scan_paths=["harness/tools"],
        connector_health_check=False,
    )
    state = await bootstrap(settings)
    candidates = state.capability_index.search(
        "Research our top competitor Acme Corp and write a positioning brief", k=3
    )
    assert candidates
    assert candidates[0].name == "competitor_research"
    assert candidates[0].kind == "agent"


@pytest.mark.asyncio
async def test_orchestrator_markdown_to_pdf_skill():
    settings = HarnessSettings(
        scan_paths=["harness/tools", "harness/skills"],
        connector_health_check=False,
    )
    state = await bootstrap(settings)
    result = await state.orchestrator.handle(
        IncomingRequest(
            message="Turn my meeting notes into a PDF.",
            skill_input={
                "markdown": "# Meeting Notes\n\n- Discussed Q3 pipeline\n- Action: follow up",
                "title": "Team Sync",
            },
        )
    )
    assert result.status == "success"
    assert result.route["selected"] == "markdown_to_pdf"
    assert result.output is not None
    assert "artifact_url" in result.output
    assert result.artifacts
    assert any(event.get("selected") == "markdown_to_pdf" for event in result.events)
    assert any(event.get("event_type") == "tool" for event in result.events)


@pytest.mark.asyncio
async def test_orchestrator_spawns_competitor_research_agent():
    settings = HarnessSettings(
        scan_paths=["harness/tools"],
        connector_health_check=False,
    )
    state = await bootstrap(settings)
    result = await state.orchestrator.handle(
        IncomingRequest(
            message="Research competitor Acme Corp and draft a positioning brief.",
        )
    )
    assert result.status == "success"
    assert result.route["selected"] == "competitor_research"
    assert result.route["kind"] == "agent"
    assert result.output is not None
    assert result.output.get("competitor") == "Acme Corp"
    assert "positioning_summary" in result.output
    assert any(event.get("event_type") == "handoff" for event in result.events)
    assert any(event.get("event_type") == "tool" for event in result.events)


@pytest.mark.asyncio
async def test_telemetry_ledger_lists_trace_events():
    settings = HarnessSettings(
        scan_paths=["harness/tools"],
        connector_health_check=False,
    )
    state = await bootstrap(settings)
    result = await state.orchestrator.handle(
        IncomingRequest(message="Research competitor Beta Inc and draft a positioning brief.")
    )
    ledger_events = state.telemetry.list_events_for_trace(result.trace_id)
    assert ledger_events
    assert any(e.get("event_type") == "routing" for e in ledger_events)


@pytest.mark.asyncio
async def test_handle_http_endpoint():
    settings = HarnessSettings(
        scan_paths=["harness/tools", "harness/skills"],
        connector_health_check=False,
    )
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/handle",
                json={
                    "message": "Convert markdown to pdf",
                    "skill_input": {"markdown": "# Hello", "title": "Doc"},
                },
            )
    assert response.status_code == 200
    body = response.json()
    assert body["route"]["selected"] == "markdown_to_pdf"


@pytest.mark.asyncio
async def test_admin_events_endpoint():
    settings = HarnessSettings(
        scan_paths=["harness/tools"],
        connector_health_check=False,
    )
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            handle_resp = await client.post(
                "/v1/handle",
                json={"message": "Research competitor Gamma LLC and draft a positioning brief."},
            )
            trace_id = handle_resp.json()["trace_id"]
            events_resp = await client.get(f"/admin/events?trace_id={trace_id}")
    assert events_resp.status_code == 200
    body = events_resp.json()
    assert body["count"] >= 1
    assert any(e.get("event_type") == "handoff" for e in body["events"])


def test_registry_collision():
    registry = ToolRegistry()
    registry.register_tool(_TestTool())
    with pytest.raises(RegistryCollisionError):
        registry.register_tool(_TestTool())


def test_skill_missing_tool_dependency():
    registry = ToolRegistry()
    with pytest.raises(UnresolvedDependencyError):
        registry.register_skill(_DependentSkill())


def test_capability_index_scoring():
    index = CapabilityIndex()
    index.add("markdown_to_pdf", "skill", "Converts Markdown text into a formatted PDF document.", ["pdf"])
    index.add("echo", "skill", "Echoes a message back", ["utility"])
    results = index.search("meeting notes pdf", k=2)
    assert results[0].name == "markdown_to_pdf"
