from __future__ import annotations

from typing import Any


def build_waterfall(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a hierarchical waterfall from flat trace events for UI rendering."""
    nodes: list[dict[str, Any]] = []
    plan_node: dict[str, Any] | None = None
    task_nodes: dict[str, dict[str, Any]] = {}

    for event in events:
        event_type = event.get("event_type")
        if event_type == "plan":
            plan_node = {
                "kind": "plan",
                "id": event.get("plan_id"),
                "action": event.get("action"),
                "display_message": event.get("display_message"),
                "timestamp": event.get("timestamp"),
                "children": [],
            }
            nodes.append(plan_node)
        elif event_type == "plan_progress":
            if plan_node is not None:
                plan_node.setdefault("progress", []).append(
                    {
                        "completed": event.get("completed"),
                        "total": event.get("total"),
                        "running": event.get("running", []),
                        "timestamp": event.get("timestamp"),
                    }
                )
        elif event_type == "task":
            task_id = event.get("task_id", "")
            if task_id not in task_nodes:
                task_nodes[task_id] = {
                    "kind": "task",
                    "id": task_id,
                    "title": event.get("title"),
                    "assignee": {
                        "kind": event.get("assignee_kind"),
                        "name": event.get("assignee_name"),
                    },
                    "children": [],
                }
                if plan_node is not None:
                    plan_node["children"].append(task_nodes[task_id])
                else:
                    nodes.append(task_nodes[task_id])
            task_nodes[task_id].setdefault("events", []).append(
                {
                    "action": event.get("action"),
                    "display_message": event.get("display_message"),
                    "duration_ms": event.get("duration_ms"),
                    "error": event.get("error"),
                    "timestamp": event.get("timestamp"),
                }
            )
        elif event_type in ("tool", "llm", "handoff", "agent_thought"):
            child = {
                "kind": event_type,
                "display_message": event.get("display_message")
                or event.get("tool_name")
                or event.get("agent_name")
                or event.get("model"),
                "timestamp": event.get("timestamp"),
                "latency_ms": event.get("latency_ms"),
                "details": {
                    k: v
                    for k, v in event.items()
                    if k
                    not in {
                        "event_type",
                        "trace_id",
                        "span_id",
                        "parent_span_id",
                        "timestamp",
                    }
                },
            }
            if task_nodes:
                list(task_nodes.values())[-1]["children"].append(child)
            elif plan_node is not None:
                plan_node["children"].append(child)
            else:
                nodes.append(child)

    return nodes
