from __future__ import annotations

import re
from typing import Any

from harness.core.context import RunContext
from harness.telemetry.instrumentation import invoke_tool_with_telemetry


def regex_extract(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.I)
    return match.group(1).strip().rstrip(".") if match else ""


def resolve_template(value: Any, variables: dict[str, Any], step_outputs: dict[str, Any]) -> Any:
    if isinstance(value, str):
        if value.startswith("{{") and value.endswith("}}"):
            return _resolve_path(value[2:-2].strip(), variables, step_outputs)
        try:
            return value.format(**{k: str(v) for k, v in variables.items()})
        except KeyError:
            return value
    if isinstance(value, dict):
        return {k: resolve_template(v, variables, step_outputs) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_template(item, variables, step_outputs) for item in value]
    return value


def _resolve_path(path: str, variables: dict[str, Any], step_outputs: dict[str, Any]) -> Any:
    if path.startswith("steps."):
        parts = path.split(".", 2)
        if len(parts) == 3:
            _, step_name, field = parts
            step_data = step_outputs.get(step_name, {})
            if isinstance(step_data, dict):
                return step_data.get(field, "")
            return step_data
    return variables.get(path, "")


async def run_configured_stub(
    *,
    stub_config: dict[str, Any],
    objective: str,
    context: RunContext,
) -> dict[str, Any]:
    """Execute a declarative stub pipeline defined in agent YAML config."""
    variables: dict[str, Any] = {"objective": objective}
    for var_name, pattern in stub_config.get("extract", {}).items():
        variables[var_name] = regex_extract(objective, pattern)

    step_outputs: dict[str, Any] = {}
    for index, step in enumerate(stub_config.get("steps", [])):
        tool_name = step["tool"]
        tool = context.tools.get(tool_name)
        if tool is None:
            continue
        step_key = step.get("as") or tool_name or f"step_{index}"
        args_payload = resolve_template(step.get("args", {}), variables, step_outputs)
        args = tool.spec.input_schema(**args_payload)
        result = await invoke_tool_with_telemetry(
            tool_name,
            tool,
            args,
            context=context,
            rationale=step.get("rationale", f"Stub step: {tool_name}"),
        )
        step_outputs[step_key] = result.model_dump() if hasattr(result, "model_dump") else result

    output_template = stub_config.get("output", {})
    return resolve_template(output_template, variables, step_outputs)
