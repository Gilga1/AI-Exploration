from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from harness.core.errors import BootstrapValidationError
from harness.core.models import ExecutionMode
from harness.registry.decorators import bind_registries
from harness.registry.data_sources import DataSourceRegistry
from harness.registry.registry import ToolRegistry
from harness.settings import HarnessSettings


def discover_packages(settings: HarnessSettings) -> list[str]:
    """Import plugin modules from configured scan directories."""
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


def validate_registry(
    registry: ToolRegistry,
    *,
    strict_sandbox: bool = True,
) -> None:
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


async def bootstrap(
    settings: HarnessSettings | None = None,
) -> tuple[ToolRegistry, DataSourceRegistry, list[str]]:
    settings = settings or HarnessSettings()
    tool_registry = ToolRegistry()
    connector_registry = DataSourceRegistry()
    bind_registries(tool_registry, connector_registry)

    imported = discover_packages(settings)
    validate_registry(tool_registry, strict_sandbox=settings.strict_sandbox_validation)

    if settings.connector_health_check and connector_registry.connectors:
        await connector_registry.health_check_all(fail_fast=settings.connector_fail_fast)

    await tool_registry.build_capability_index()
    return tool_registry, connector_registry, imported


def _module_name(py_file: Path) -> str:
    return f"harness_plugin.{py_file.stem}_{abs(hash(py_file)) & 0xFFFF:X}"
