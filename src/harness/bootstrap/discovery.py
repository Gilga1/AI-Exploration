from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from harness.agents.loader import load_yaml_agents
from harness.agents.profile_loader import AgentProfileRegistry, load_agent_profiles
from harness.bootstrap.state import BootstrapState
from harness.config.loader import load_config_plane
from harness.connectors.factory import build_connector
from harness.core.errors import BootstrapValidationError
from harness.core.models import ExecutionMode
from harness.hitl.store import ApprovalStore
from harness.memory.manager import MemoryManager
from harness.mcp.discovery import discover_mcp_tools
from harness.orchestrator.orchestrator import Orchestrator
from harness.orchestrator.plan_store import PlanStore
from harness.orchestrator.workflow_loader import load_workflow_templates
from harness.orchestrator.workflow_registry import WorkflowRegistry
from harness.registry.decorators import bind_registries
from harness.registry.data_sources import DataSourceRegistry
from harness.registry.registry import ToolRegistry
from harness.routing.capability_index import CapabilityIndex
from harness.routing.router import TieredRouter
from harness.settings import HarnessSettings
from harness.telemetry.bus import TelemetryBus


def discover_packages(settings: HarnessSettings) -> list[str]:
    imported: list[str] = []
    for package_path in settings.scan_paths:
        path = Path(package_path)
        if not path.is_dir():
            continue
        for py_file in sorted(path.rglob("*.py")):
            if py_file.name.startswith("_"):
                continue
            module_name = _module_name(py_file)
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            imported.append(module_name)
    return imported


def validate_registry(registry: ToolRegistry, *, strict_sandbox: bool = True) -> None:
    errors: list[str] = []

    for tool in registry.tools.values():
        if tool.spec.requires_approval and not tool.spec.side_effects:
            errors.append(
                f"Tool {tool.spec.name!r} requires approval but side_effects is false"
            )

    for skill in registry.skills.values():
        missing = set(skill.manifest.required_tools) - registry.tools.keys()
        if missing:
            errors.append(
                f"Skill {skill.manifest.name!r} missing required tools: {sorted(missing)}"
            )
        if skill.manifest.sandboxed:
            for tool_name in skill.manifest.required_tools:
                tool = registry.tools.get(tool_name)
                if tool and tool.spec.execution_mode == ExecutionMode.IN_PROCESS:
                    errors.append(
                        f"Skill {skill.manifest.name!r} is sandboxed but tool "
                        f"{tool_name!r} runs in_process"
                    )

    for agent in registry.agents.values():
        for tool_name in agent.manifest.allowed_tools:
            if tool_name not in registry.tools:
                errors.append(
                    f"Agent {agent.manifest.name!r} references unknown tool {tool_name!r}"
                )
        for skill_name in agent.manifest.allowed_skills:
            if skill_name not in registry.skills:
                errors.append(
                    f"Agent {agent.manifest.name!r} references unknown skill {skill_name!r}"
                )

    if errors:
        raise BootstrapValidationError(errors)


def _build_capability_index(registry: ToolRegistry, config) -> CapabilityIndex:
    index = CapabilityIndex()
    for skill in registry.skills.values():
        index.add(
            skill.manifest.name,
            "skill",
            skill.manifest.description,
            skill.manifest.capability_tags,
        )
    for agent in registry.agents.values():
        index.add(
            agent.manifest.name,
            "agent",
            agent.manifest.description,
            agent.manifest.capability_tags,
        )
    for pack in config.context_packs:
        if not pack.always_inject:
            index.add(
                pack.name,
                "skill",
                pack.description,
                list(pack.scope.get("agent_tags", [])),
            )
    registry._capability_index = index
    return index


async def bootstrap(settings: HarnessSettings | None = None) -> BootstrapState:
    settings = settings or HarnessSettings.load()
    config = load_config_plane(settings.config_root)

    tool_registry = ToolRegistry()
    connector_registry = DataSourceRegistry()
    bind_registries(tool_registry, connector_registry)

    for connector_config in config.connectors:
        connector_registry.register_connector(build_connector(connector_config))

    imported = discover_packages(settings)
    telemetry = TelemetryBus(
        content_sample_rate=settings.telemetry_content_sample_rate,
        enable_otel=settings.telemetry_enable_otel,
        enable_ledger=settings.telemetry_enable_ledger,
        ledger_db_path=settings.telemetry_ledger_db_path,
        langfuse_enabled=settings.langfuse_enabled,
    )
    approval_store = ApprovalStore(settings.approvals_db_path)
    plan_store = PlanStore(settings.orchestration_plans_db_path)
    workflow_templates = load_workflow_templates(Path(settings.config_root) / "workflows")
    workflow_registry = WorkflowRegistry(
        workflow_templates,
        settings=settings,
        config=config,
    )
    memory = MemoryManager(
        reflective_conn=next(iter(connector_registry.connectors.values()), None),
        episodic_db_path=settings.episodic_db_path,
    )

    if settings.mcp_enabled:
        mcp_loaded = await discover_mcp_tools(config.mcp, tool_registry)
        imported.extend(mcp_loaded)

    yaml_agents = load_yaml_agents(
        settings.config_root,
        config,
        tool_registry,
        telemetry=telemetry,
        approval_store=approval_store,
        force_stub_models=settings.force_stub_models,
        checkpointer=memory.working,
        connectors=connector_registry.connectors,
    )
    imported.extend(yaml_agents)

    profile_registry = load_agent_profiles(
        settings.config_root,
        config=config,
        registry=tool_registry,
        telemetry=telemetry,
        approval_store=approval_store,
        force_stub_models=settings.force_stub_models,
        checkpointer=memory.working,
        connectors=connector_registry.connectors,
    )
    imported.extend([f"profile:{profile.name}" for profile in profile_registry.profiles])

    validate_registry(tool_registry, strict_sandbox=settings.strict_sandbox_validation)

    if settings.connector_health_check and connector_registry.connectors:
        await connector_registry.health_check_all(fail_fast=settings.connector_fail_fast)

    capability_index = _build_capability_index(tool_registry, config)
    router = TieredRouter(capability_index, settings, telemetry, config=config)
    orchestrator = Orchestrator(
        tool_registry,
        router,
        memory,
        telemetry,
        settings,
        approval_store=approval_store,
        connector_registry=connector_registry,
    )
    orchestrator.set_plan_store(plan_store)
    orchestrator.set_workflow_registry(workflow_registry)

    return BootstrapState(
        settings=settings,
        config=config,
        tool_registry=tool_registry,
        connector_registry=connector_registry,
        capability_index=capability_index,
        memory=memory,
        telemetry=telemetry,
        router=router,
        orchestrator=orchestrator,
        approval_store=approval_store,
        plan_store=plan_store,
        workflow_registry=workflow_registry,
        profile_registry=profile_registry,
        imported_modules=imported,
    )


def _module_name(py_file: Path) -> str:
    return f"harness_plugin.{py_file.stem}_{abs(hash(py_file)) & 0xFFFF:X}"
