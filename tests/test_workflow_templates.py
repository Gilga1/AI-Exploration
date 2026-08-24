from __future__ import annotations

import pytest

from harness.bootstrap import bootstrap
from harness.core.request import IncomingRequest
from harness.orchestrator.workflow_loader import load_workflow_templates
from harness.orchestrator.workflow_models import WorkflowTemplate, WorkflowVariableSpec
from harness.orchestrator.workflow_registry import WorkflowRegistry, extract_variables
from harness.settings import HarnessSettings


def _settings(**kwargs) -> HarnessSettings:
    defaults = dict(
        scan_paths=["harness/tools", "harness/skills"],
        connector_health_check=False,
        force_stub_models=True,
        langfuse_enabled=False,
        orchestration_mode="multi",
        orchestration_require_plan_approval=True,
        orchestration_planner="auto",
    )
    defaults.update(kwargs)
    return HarnessSettings(**defaults)


def test_load_workflow_templates_from_harness_dir():
    templates = load_workflow_templates("harness/workflows")
    assert len(templates) >= 1
    names = {template.name for template in templates}
    assert "competitive_sales_brief" in names


def test_variable_substitution_and_extraction():
    template = WorkflowTemplate(
        name="demo",
        description="demo",
        match_tags=["competitor", "sales"],
        variables={
            "competitor": WorkflowVariableSpec(
                extract=r"competitor\s+([A-Za-z0-9][\w .'-]+?)(?=\s+and\b|\s+sales\b|\s*[,.]|$)",
                default="the competitor",
            ),
            "advisor_name": WorkflowVariableSpec(
                extract=r"advisor\s+([A-Za-z][A-Za-z .'-]+?)(?=\s+sales\b|\s+product\b|\s*[,.]|$)",
                default="the advisor",
            ),
        },
        tasks=[],
    )
    message = "Research competitor Beta Inc and analyze advisor John Smith sales."
    values = extract_variables(message, template)
    assert values["competitor"] == "Beta Inc"
    assert values["advisor_name"] == "John Smith"


def test_workflow_registry_matches_template():
    templates = load_workflow_templates("harness/workflows")
    registry = WorkflowRegistry(templates, settings=_settings())
    message = "Research competitor Beta Inc and analyze advisor John Smith product sales."
    plan = registry.try_build_plan(message, mode="auto")
    assert plan is not None
    assert "competitive_sales_brief" in plan.rationale
    assert len(plan.tasks) == 2
    assert plan.tasks[0].assignee_name == "competitor_research"
    assert "Beta Inc" in plan.tasks[0].objective
    assert plan.tasks[1].assignee_name == "agentic_analyzer"
    assert "John Smith" in plan.tasks[1].objective


def test_template_mode_returns_empty_plan_when_no_match():
    registry = WorkflowRegistry([], settings=_settings(orchestration_planner="template"))
    from harness.orchestrator.planner import Planner

    planner = Planner(
        registry=object(),  # type: ignore[arg-type]
        capability_index=object(),  # type: ignore[arg-type]
        config=object(),  # type: ignore[arg-type]
        settings=_settings(orchestration_planner="template"),
        workflows=registry,
    )
    plan = planner.create_plan(
        IncomingRequest(message="Tell me a joke about databases.")
    )
    assert plan.tasks == []
    assert "No workflow template matched" in plan.rationale


@pytest.mark.asyncio
async def test_auto_planner_uses_workflow_template():
    state = await bootstrap(_settings(orchestration_planner="auto"))
    assert state.workflow_registry.templates
    result = await state.orchestrator.handle(
        IncomingRequest(
            message="Research competitor Beta Inc and analyze advisor John Smith product sales.",
            orchestration={"mode": "multi"},
        )
    )
    assert result.status == "awaiting_plan_approval"
    assert result.plan is not None
    assert "competitive_sales_brief" in result.plan["rationale"]
    assert len(result.plan["tasks"]) == 2


@pytest.mark.asyncio
async def test_plan_hitl_still_required_for_workflow_template():
    state = await bootstrap(_settings(orchestration_planner="template"))
    result = await state.orchestrator.handle(
        IncomingRequest(
            message="Research competitor Gamma LLC and analyze advisor Jane Doe sales by product.",
            orchestration={"mode": "multi"},
        )
    )
    assert result.status == "awaiting_plan_approval"
    assert result.task_id == result.plan["plan_id"]
