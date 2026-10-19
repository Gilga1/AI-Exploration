export type PromptLauncherId =
  | "open_fleet_ops"
  | "delayed_vans_today"
  | "region_ops_report"
  | "incident_playbook"
  | "open_ops_board"
  | "fleet_briefing_story";

/** User-message text shared by MCP prompts and in-app “Run now” buttons. */
export function openFleetOpsPromptText(): string {
  return `Open the **Fleet Ops** connector (Territory Trade–style MCP App).

Follow these exact steps. Do not skip any.
1. Call the \`open_fleet_ops\` tool with view "overview".
2. Tell me the host display mode and width the app reports.
3. Offer to switch to the live map or operations board.

If the prompt attached as a file pill, treat this message as the user request.`;
}

export function delayedVansTodayPromptText(): string {
  return `List vans with delay or a critical hold in the mocked San Francisco fleet today (Territory Trade “trade today” analog).

Follow these exact steps. Do not skip any.
1. If a glossary resource is attached, use those status labels.
2. Call \`list_delayed_vans\` for the Markdown table.
3. Call \`show_live_map\` so I can see them on the map.
4. Keep the MCP App on the map. Do not dump every lat/lng into chat.`;
}

export function regionOpsReportPromptText(region: string): string {
  return `You are a senior operations analyst. Generate a region report for **${region}** (weekly sales report analog).

Follow these exact steps. Do not skip any.
1. Call \`get_region_summary\` with region ${region}.
2. Call \`show_operations_dashboard\`.
3. Use attached resources if present (\`ops://glossary\`, \`ops://dashboard-schema\`, \`ops://region/${region}\`).
4. Compare ${region} on-time %, volume, and incidents against the other regions.
5. Output a Markdown table of all regions, with ${region} first, plus a 3-bullet recommendation.
6. Do not invent vans that are not in the tool results.`;
}

export function incidentPlaybookPromptText(vehicleId?: string): string {
  const focus = vehicleId?.trim() || "the most severe open alert";
  return `Run the incident playbook for ${focus}.

Follow these exact steps. Do not skip any.
1. Call \`show_sheet_patterns\` so the MCP App opens the sheets view.
2. Identify the matching alert from the tool result.
3. Recommend Confirm, Snooze, or hand off to Claude for judgment — then ask me which to take.
4. Confirm/Snooze stay in-app (no new tools). Judgment uses the app's Explain/Discuss path (Desktop: composer + Send).`;
}

export function openOpsBoardPromptText(): string {
  return `Open the **operations board** for today's mocked San Francisco fleet.

Follow these exact steps. Do not skip any.
1. Call \`show_operations_dashboard\`.
2. Summarize each KPI in one sentence. Remind me that clicking a metric shows the mock query in-app; **Refresh** and filters use tools without a Claude turn; **Explain** fills the composer for my judgment.
3. Call out Mission if on-time lags the city.
4. Keep the MCP App on the dashboard.
5. Do not claim this is Claude Dashboards — that is a separate Anthropic product (see ops://claude-product-notes).`;
}

export function fleetBriefingStoryPromptText(): string {
  return `Open the **fleet briefing** CSS scene (POC only — not Claude Motion / MP4).

Follow these exact steps. Do not skip any.
1. Call \`show_fleet_briefing\`.
2. Narrate the short story: on-time trend, delayed vans, and the critical dock hold.
3. Remind me Motion MP4 export lives in Claude's product Artifacts, not this connector.
4. Keep the MCP App on the briefing view while narrating.`;
}

export function promptTextForLauncher(id: PromptLauncherId, region = "SOMA"): string {
  switch (id) {
    case "open_fleet_ops":
      return openFleetOpsPromptText();
    case "delayed_vans_today":
      return delayedVansTodayPromptText();
    case "region_ops_report":
      return regionOpsReportPromptText(region);
    case "incident_playbook":
      return incidentPlaybookPromptText();
    case "open_ops_board":
      return openOpsBoardPromptText();
    case "fleet_briefing_story":
      return fleetBriefingStoryPromptText();
    default:
      return openFleetOpsPromptText();
  }
}
