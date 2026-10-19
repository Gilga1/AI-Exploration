export type PromptLauncherId =
  | "open_gallery"
  | "delayed_vans_today"
  | "region_ops_report"
  | "incident_playbook"
  | "open_ops_dashboard"
  | "animate_fleet_briefing";

/** User-message text shared by MCP prompts and in-app “Run now” buttons. */
export function openGalleryPromptText(): string {
  return `Open the MCP Apps exploration gallery.

Follow these exact steps. Do not skip any.
1. Call the \`explore_mcp_apps\` tool with view "overview".
2. Tell me the host display mode and width the app reports.
3. Offer to switch to the live map or operations dashboard.

If the prompt attached as a file pill, treat this message as the user request.`;
}

export function delayedVansTodayPromptText(): string {
  return `List vans with delay or a critical hold in the mocked San Francisco fleet today.

Follow these exact steps. Do not skip any.
1. If a glossary resource is attached, use those status labels. Otherwise call nothing extra for definitions.
2. Call the \`show_live_map\` tool.
3. From the tool result, list vans with status \`delayed\` and any critical alerts.
4. Output a Markdown table: van id, driver, status, load, ETA minutes, and a one-line next action.
5. Keep the MCP App on the map. Do not dump every lat/lng into chat.`;
}

export function regionOpsReportPromptText(region: string): string {
  return `You are a senior operations analyst. Generate a region report for **${region}**.

Follow these exact steps. Do not skip any.
1. Call \`show_operations_dashboard\`.
2. Use attached resources if present (\`ops://glossary\`, \`ops://dashboard-schema\`, \`ops://region/${region}\`).
3. Compare ${region} on-time %, volume, and incidents against the other regions.
4. Output a Markdown table of all regions, with ${region} first, plus a 3-bullet recommendation.
5. Do not skip the tool call. Do not invent vans that are not in the tool result.`;
}

export function incidentPlaybookPromptText(vehicleId?: string): string {
  const focus = vehicleId?.trim() || "the most severe open alert";
  return `Run the incident playbook for ${focus}.

Follow these exact steps. Do not skip any.
1. Call \`show_sheet_patterns\` so the MCP App opens the sheets view.
2. Identify the matching alert from the tool result.
3. Recommend Confirm, Snooze, or Ask Claude — then ask me which to take.
4. If I want Claude to help, wait; the app button already uses sendMessage. Do not re-call tools unless I ask.`;
}

/** Inspired by Claude Dashboards: live KPIs with transparent queries. */
export function openOpsDashboardPromptText(): string {
  return `Build and walk me through the **operations dashboard** for today's mocked San Francisco fleet (Claude Dashboards-style).

Follow these exact steps. Do not skip any.
1. Call \`show_operations_dashboard\` (or \`explore_mcp_apps\` with view "dashboard").
2. Summarize each KPI card in one sentence. When I click a number in the app, explain the mock query behind it.
3. Compare regions in the table and call out Mission if on-time lags the city.
4. Keep the MCP App on the dashboard. Do not paste every sparkline value into chat.
5. Offer to open the fleet motion explainer if I need an all-hands animation.`;
}

/** Inspired by Claude Motion: code-built explainer, not generated video. */
export function animateFleetBriefingPromptText(): string {
  return `Turn today's fleet story into a short **motion explainer** inside the MCP App (Claude Motion-style).

Follow these exact steps. Do not skip any.
1. Call \`show_fleet_motion\` to open the animation view.
2. Narrate the 30-second story: on-time trend, delayed vans, and the critical dock hold.
3. Offer to tweak timing or copy — the animation is code in the iframe, not AI-generated footage.
4. Keep the MCP App on the motion view while narrating.`;
}

export function explainDashboardKpiPromptText(kpiId: string, label: string, value: number, unit: string): string {
  return `Explain the **${label}** KPI (${value}${unit}) on the operations dashboard.

1. Call \`show_operations_dashboard\` if the app is not already open.
2. Show the mock SQL behind metric id \`${kpiId}\` and what would change it today.
3. Give one recommended action for ops.`;
}

export function explainDashboardRegionPromptText(region: string, onTimePct: number): string {
  return `Explain the **${region}** row (${onTimePct}% on-time) on the operations dashboard and whether we should reroute vans.`;
}

export function promptTextForLauncher(id: PromptLauncherId, region = "SOMA"): string {
  switch (id) {
    case "open_gallery":
      return openGalleryPromptText();
    case "delayed_vans_today":
      return delayedVansTodayPromptText();
    case "region_ops_report":
      return regionOpsReportPromptText(region);
    case "incident_playbook":
      return incidentPlaybookPromptText();
    case "open_ops_dashboard":
      return openOpsDashboardPromptText();
    case "animate_fleet_briefing":
      return animateFleetBriefingPromptText();
    default:
      return openGalleryPromptText();
  }
}
