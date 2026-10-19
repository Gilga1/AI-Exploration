import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { KPI_QUERY_BEHIND, regionQueryBehind } from "../src/dashboard-queries.ts";
import { openOpsBoardPromptText, promptTextForLauncher } from "../src/prompt-copy.ts";

describe("prompt copy", () => {
  it("maps launcher ids to connector recipes", () => {
    assert.match(promptTextForLauncher("open_fleet_ops"), /open_fleet_ops/);
    assert.match(promptTextForLauncher("fleet_briefing_story"), /show_fleet_briefing/);
    assert.match(promptTextForLauncher("delayed_vans_today"), /list_delayed_vans/);
    assert.match(openOpsBoardPromptText(), /show_operations_dashboard/);
    assert.match(openOpsBoardPromptText(), /Claude Dashboards/);
    assert.match(openOpsBoardPromptText(), /separate Anthropic product/);
  });

  it("includes mock SQL for each KPI id", () => {
    assert.ok(KPI_QUERY_BEHIND.ontime?.includes("on_time_pct"));
    assert.ok(KPI_QUERY_BEHIND.incidents?.includes("ops_alerts"));
  });

  it("builds region query snippets", () => {
    assert.match(regionQueryBehind("Mission", 88, 98), /Mission/);
  });
});
