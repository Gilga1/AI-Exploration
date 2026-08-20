from __future__ import annotations

import re

from qwen_agentic_ft.extract.parser import CodeChunk

PATTERN_INSTRUCTIONS: dict[str, str] = {
    "create_deep_agent": "Create a Deep Agent using create_deep_agent with appropriate tools and system prompt.",
    "state_graph": "Build a LangGraph StateGraph with nodes, edges, and compiled execution.",
    "create_agent": "Create a LangChain agent with model binding, tools, and invoke loop.",
    "tool_decorator": "Define LangChain tools using the @tool decorator with clear docstrings.",
    "checkpointer": "Add persistence/checkpointing to a LangGraph agent using a checkpointer.",
    "subagent": "Implement subagent delegation so a supervisor agent can assign tasks.",
    "hitl": "Add human-in-the-loop approval before sensitive tool execution.",
    "backend": "Configure a Deep Agents filesystem backend for read/write operations.",
}


def _clean_docstring(doc: str) -> str:
    doc = re.sub(r"\s+", " ", doc).strip()
    return doc[:500]


def instruction_from_chunk(chunk: CodeChunk) -> str | None:
    if chunk.docstring and len(chunk.docstring) >= 20:
        doc = _clean_docstring(chunk.docstring)
        if chunk.chunk_type in {"FunctionDef", "AsyncFunctionDef"}:
            return f"Implement a Python function named `{chunk.name}` that: {doc}"
        if chunk.chunk_type == "ClassDef":
            return f"Implement a Python class named `{chunk.name}` that: {doc}"
        return f"Write Python code that: {doc}"

    if chunk.patterns:
        primary = chunk.patterns[0]
        base = PATTERN_INSTRUCTIONS.get(primary, "Write agentic Python code for the LangChain ecosystem.")
        if chunk.name and chunk.name not in {"__init__", "main"}:
            return f"{base} Name the primary entry `{chunk.name}`."
        return base

    path_hint = chunk.source_file.replace("/", " ").replace("_", " ").replace(".py", "")
    import_hint = ", ".join(
        i for i in chunk.imports if any(k in i for k in ("langchain", "langgraph", "deepagents"))
    )
    if import_hint:
        return f"Write agentic Python code for `{path_hint}` using imports such as {import_hint}."
    return f"Write agentic Python code implementing the patterns in `{chunk.source_file}`."
