import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { KPI_QUERY_BEHIND, regionQueryBehind } from "../src/dashboard-queries.ts";
import { openOpsDashboardPromptText, promptTextForLauncher } from "../src/prompt-copy.ts";

describe("prompt copy", () => {
  it("maps launcher ids to the same recipes as MCP prompts", () => {
    assert.match(promptTextForLauncher("open_gallery"), /explore_mcp_apps/);
    assert.match(promptTextForLauncher("animate_fleet_briefing"), /show_fleet_motion/);
    assert.match(openOpsDashboardPromptText(), /show_operations_dashboard/);
  });

  it("includes mock SQL for each KPI id", () => {
    assert.ok(KPI_QUERY_BEHIND.ontime?.includes("on_time_pct"));
    assert.ok(KPI_QUERY_BEHIND.incidents?.includes("ops_alerts"));
  });

  it("builds region query snippets", () => {
    assert.match(regionQueryBehind("Mission", 88, 98), /Mission/);
  });
});
