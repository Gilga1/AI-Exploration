from __future__ import annotations

from typing import Any

from harness.config.models import MCPServerConfig, MCPServersConfig
from harness.core.context import RunContext
from harness.core.models import ExecutionMode, ToolSpec
from harness.registry.registry import ToolRegistry


async def discover_mcp_tools(mcp_config: MCPServersConfig, registry: ToolRegistry) -> list[str]:
    """Load tools from enabled MCP servers into the tool registry."""
    enabled = [s for s in mcp_config.servers if s.enabled]
    if not enabled:
        return []

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        return []

    server_configs = {server.name: _to_client_config(server) for server in enabled}
    client = MultiServerMCPClient(server_configs)
    loaded: list[str] = []

    try:
        mcp_tools = await client.get_tools()
    except Exception:
        return loaded

    for mcp_tool in mcp_tools:
        server_prefix = _server_prefix(mcp_tool.name, enabled)
        harness_name = f"{server_prefix}_{mcp_tool.name}" if server_prefix else mcp_tool.name
        wrapper = _HarnessMCPTool(mcp_tool, harness_name)
        try:
            registry.register_tool(wrapper)
            loaded.append(harness_name)
        except Exception:
            continue
    return loaded


def _to_client_config(server: MCPServerConfig) -> dict[str, Any]:
    if server.transport == "stdio":
        return {
            "transport": "stdio",
            "command": server.command,
            "args": server.args,
        }
    return {
        "transport": server.transport,
        "url": server.url,
        "headers": server.headers,
    }


def _server_prefix(tool_name: str, servers: list[MCPServerConfig]) -> str:
    for server in servers:
        if tool_name.startswith(f"{server.name}_"):
            return ""
    if len(servers) == 1:
        return servers[0].name
    return ""


class _HarnessMCPTool:
    def __init__(self, mcp_tool: Any, name: str) -> None:
        self._mcp_tool = mcp_tool
        self.spec = ToolSpec(
            name=name,
            description=getattr(mcp_tool, "description", "") or f"MCP tool {name}",
            input_schema=_generic_schema(),
            output_schema=_generic_schema(),
            side_effects=True,
            requires_approval=True,
            execution_mode=ExecutionMode.SUBPROCESS,
        )

    async def run(self, args: Any, *, context: RunContext) -> Any:
        payload = args.model_dump() if hasattr(args, "model_dump") else dict(args)
        return await self._mcp_tool.ainvoke(payload)


def _generic_schema():
    from pydantic import BaseModel

    class GenericMCPInput(BaseModel):
        model_config = {"extra": "allow"}

    return GenericMCPInput
