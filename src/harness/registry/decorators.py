from __future__ import annotations

from typing import Callable, TypeVar

from harness.core.protocols import BaseAgent, BaseDataConnector, BaseSkill, BaseTool
from harness.registry.data_sources import DataSourceRegistry
from harness.registry.registry import ToolRegistry

T = TypeVar("T", BaseTool, BaseSkill, BaseAgent, BaseDataConnector)

_tool_registry: ToolRegistry | None = None
_connector_registry: DataSourceRegistry | None = None


def _get_tool_registry() -> ToolRegistry:
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry


def _get_connector_registry() -> DataSourceRegistry:
    global _connector_registry
    if _connector_registry is None:
        _connector_registry = DataSourceRegistry()
    return _connector_registry


def bind_registries(
    tool_registry: ToolRegistry,
    connector_registry: DataSourceRegistry,
) -> None:
    global _tool_registry, _connector_registry
    _tool_registry = tool_registry
    _connector_registry = connector_registry


def register_tool(cls: type[T]) -> type[T]:
    instance = cls()
    _get_tool_registry().register_tool(instance)  # type: ignore[arg-type]
    return cls


def register_skill(cls: type[T]) -> type[T]:
    instance = cls()
    _get_tool_registry().register_skill(instance)  # type: ignore[arg-type]
    return cls


def register_agent(cls: type[T]) -> type[T]:
    instance = cls()
    _get_tool_registry().register_agent(instance)  # type: ignore[arg-type]
    return cls


def register_connector(cls: type[T]) -> type[T]:
    instance = cls()
    _get_connector_registry().register_connector(instance)  # type: ignore[arg-type]
    return cls


def registration_callback(
    kind: str,
    register_fn: Callable[[object], None],
) -> Callable[[type], type]:
    def decorator(cls: type) -> type:
        register_fn(cls())
        return cls

    return decorator
