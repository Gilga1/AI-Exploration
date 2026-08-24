from __future__ import annotations

from pathlib import Path

import yaml

from harness.config.secrets import resolve_tree
from harness.orchestrator.workflow_models import WorkflowTemplate, WorkflowVariableSpec


def load_workflow_templates(workflows_dir: str | Path) -> list[WorkflowTemplate]:
    root = Path(workflows_dir)
    if not root.is_dir():
        return []

    templates: list[WorkflowTemplate] = []
    for yaml_file in sorted(root.glob("*.yaml")):
        data = resolve_tree(yaml.safe_load(yaml_file.read_text()) or {})
        if not data:
            continue
        templates.append(_parse_template(data))
    return templates


def _parse_template(data: dict) -> WorkflowTemplate:
    variables_raw = data.get("variables") or {}
    variables: dict[str, WorkflowVariableSpec] = {}
    if isinstance(variables_raw, list):
        for name in variables_raw:
            variables[name] = WorkflowVariableSpec()
    else:
        for name, spec in variables_raw.items():
            if isinstance(spec, str):
                variables[name] = WorkflowVariableSpec(extract=spec)
            elif isinstance(spec, dict):
                variables[name] = WorkflowVariableSpec(**spec)
            else:
                variables[name] = WorkflowVariableSpec()

    payload = {k: v for k, v in data.items() if k != "variables"}
    payload["variables"] = variables
    return WorkflowTemplate(**payload)
