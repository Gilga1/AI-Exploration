# Claude product features vs this MCP connector

This file is the source of truth for **what Claude Dashboards / Motion are** and **what this repo is not**.

## Claude Dashboards & Claude Motion (Anthropic product)

These are **first-party Claude features**, not MCP Apps and not this connector.

| Product | Where | What you get |
| --- | --- | --- |
| **Claude Dashboards** | Claude chat / Artifacts (paid; may need admin enable) | Connect BigQuery, Snowflake, Databricks, Salesforce, etc. Ask in plain language. Live charts. Click a number → see the **real** query. Refresh as data changes. Export / hand off to BI tools. |
| **Claude Motion** | Claude chat / Artifacts (Team & Enterprise beta) | Claude writes **animation code** in an editor. Play like a short video. Edit timing/copy. Download **MP4**. Open in Adobe, Runway, etc. Not generative video footage. |
| **Docs / Slides / Design** | Claude Artifacts (generally available) | Docs, decks, designs in conversation. |

Announcement: [Build live dashboards and animate explainers with Claude](https://claude.com/resources/articles/dashboards-and-motion).

**How to try them:** Open Claude (not this MCP server). Use Organization settings → Artifacts if your admin has Dashboards/Motion off. Ask e.g. “Build a dashboard of this quarter’s revenue by region” or “Animate how our pricing plans compare.”

## This repo: Fleet Ops MCP Apps connector

Territory Trade Report–style **custom connector**:

- **Tools** return ops data and/or open an MCP App UI (live map, ops board, sheets).
- **Prompts** (+ menu) are named recipes for common jobs.
- **Resources** (`ops://…`) are read-only grounding (glossary, entitlements, snapshot).
- **In-app clicks** mostly call **`callServerTool`** (filter / refresh / drill-down) with **no** Claude turn.
- **Explain / judgment** uses `sendMessage`, which on **Claude Desktop only fills the composer** — you still press Send ([claude-ai-mcp#33](https://github.com/anthropics/claude-ai-mcp/issues/33)).

| Do not expect from this connector | Use instead |
| --- | --- |
| Real warehouse SQL / live CRM | Claude Dashboards + your data connectors |
| MP4 motion export / Motion editor | Claude Motion in Claude |
| One-click auto-send without Enter on Desktop | Not available — host safety design |

The **Briefing** tab is a CSS mock explainer for UX experiments. It is **not** Claude Motion.
