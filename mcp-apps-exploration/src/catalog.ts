/**
 * MCP prompts and read-only resources for the fleet gallery.
 *
 * Analog of the Territory Trade Report production shape:
 * prompts = named recipes the user picks from Claude's + menu;
 * resources = glossary / entitlements / snapshots the user attaches.
 * Live data still comes from tools + the MCP App UI.
 */
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { ResourceTemplate } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { vansForRegion } from "./fleet-ops.ts";
import { FLEET_SNAPSHOT, type RegionRow } from "./mock-data.ts";
import {
  delayedVansTodayPromptText,
  fleetBriefingStoryPromptText,
  incidentPlaybookPromptText,
  openFleetOpsPromptText,
  openOpsBoardPromptText,
  regionOpsReportPromptText,
} from "./prompt-copy.ts";

export const REGIONS = ["SOMA", "Mission", "Marina", "Sunset", "Richmond"] as const;
export type RegionName = (typeof REGIONS)[number];

export const GLOSSARY_URI = "ops://glossary";
export const MY_REGIONS_URI = "ops://my-regions";
export const DASHBOARD_SCHEMA_URI = "ops://dashboard-schema";
export const TODAY_SNAPSHOT_URI = "ops://snapshot/today";
export const CLAUDE_PRODUCT_URI = "ops://claude-product-notes";
/** @deprecated use CLAUDE_PRODUCT_URI */
export const CLAUDE_ARTIFACTS_URI = CLAUDE_PRODUCT_URI;
export const REGION_TEMPLATE = "ops://region/{region}";

export const CLAUDE_PRODUCT_NOTES_MD = `# Claude product vs Fleet Ops MCP (short)

Full write-up: \`CLAUDE_PRODUCT.md\` in the repo.

- **Claude Dashboards / Motion** = Anthropic Artifacts products (data platforms, MP4). Try them *in Claude*, not via this connector.
- **This connector** = Territory Trade–style Fleet Ops MCP App: tools, prompts, resources, in-app filter/refresh via \`callServerTool\`.
- Desktop \`sendMessage\` only fills the composer — press Send ([claude-ai-mcp#33](https://github.com/anthropics/claude-ai-mcp/issues/33)).
`;

export const GLOSSARY_MD = `# Fleet glossary (mocked)

Use these terms when writing insights. Do not invent new status labels.

| Term | Meaning |
| --- | --- |
| **Van** | Delivery vehicle (id like \`VAN-14\`). Analog of a buying unit (BU). |
| **Hub** | Depot that vans depart from (SoMa Hub, Marina Hub). Analog of a territory desk. |
| **Trade today / delayed** | A van with status \`delayed\`, or a critical hold that blocks a stop. Analog of "BUs with trade today". |
| **On-time %** | Share of stops arriving inside the promised window. |
| **Incident** | Open ops issue (traffic, charging, dock hold). |
| **Load** | What the van is carrying (cold chain, pharmacy, parcels). |

Statuses: \`en_route\`, \`idle\`, \`delayed\`, \`charging\`.
`;

export const DASHBOARD_SCHEMA_MD = `# Operations dashboard field guide

| Field | Where | How to read it |
| --- | --- | --- |
| On-time | KPI card | Percent; green if ≥ 94. |
| Active vans | KPI card | Count currently moving or delayed. |
| Median ETA | KPI card | Minutes to next stop. |
| Open incidents | KPI card | Count of warning + critical alerts. |
| Region on-time / volume / incidents | Region table | Compare one region to the city. |
| Hourly volume | Sparkline | Stops per hour, oldest → newest. |

When the MCP App is open, prefer the dashboard view over restating every number in chat.
`;

export const MY_REGIONS_MD = `# My regions (mock post-auth entitlements)

This connector pretends the signed-in user is an ISC covering:

- **SOMA** — primary desk
- **Mission** — secondary desk

Other regions (Marina, Sunset, Richmond) are visible as city context but are not in-scope for action.

Analog of "my territories" after OAuth on the Territory Trade connector.
`;

export function regionBriefing(region: string): string {
  const row = FLEET_SNAPSHOT.regions.find((r) => r.region.toLowerCase() === region.toLowerCase());
  if (!row) {
    return `# Unknown region\n\nNo mocked region named "${region}". Known: ${REGIONS.join(", ")}.`;
  }
  const vans = FLEET_SNAPSHOT.vehicles.filter((v) => vansForRegion(row.region).includes(v.id));
  const lines = [
    `# ${row.region} region briefing`,
    "",
    `- On-time: **${row.onTimePct}%**`,
    `- Volume: **${row.volume}** stops`,
    `- Incidents: **${row.incidents}**`,
    "",
    "## Vans often associated with this desk",
    "",
    vans.length
      ? vans.map((v) => `- ${v.id} · ${v.driver} · ${v.status} · ${v.load}`).join("\n")
      : "- No vans tagged to this desk in the mock.",
    "",
    "Live positions still require the `show_live_map` tool.",
  ];
  return lines.join("\n");
}

export function todaySnapshotMd(): string {
  const vans = FLEET_SNAPSHOT.vehicles
    .map((v) => `| ${v.id} | ${v.driver} | ${v.status} | ${v.load} | ${v.etaMin} min |`)
    .join("\n");
  const alerts = FLEET_SNAPSHOT.alerts.map((a) => `- **${a.severity}** ${a.title}: ${a.body}`).join("\n");
  return `# Fleet snapshot (frozen)

Generated at ${FLEET_SNAPSHOT.generatedAt} · ${FLEET_SNAPSHOT.city}

This is a **resource**, not a live query. Attach it for grounding. Call a tool if you need the MCP App.

| Van | Driver | Status | Load | ETA |
| --- | --- | --- | --- | --- |
${vans}

## Open alerts

${alerts}
`;
}

const regionArg = z
  .enum(REGIONS)
  .describe("Region desk to brief: SOMA, Mission, Marina, Sunset, or Richmond");

const vehicleArg = z
  .string()
  .optional()
  .describe("Optional van id such as VAN-07. Leave blank to let Claude pick from alerts.");

export function registerCatalog(server: McpServer): void {
  server.registerPrompt(
    "open_fleet_ops",
    {
      title: "Open Fleet Ops",
      description: "Territory Trade–style starter: open the Fleet Ops MCP App. + → Connectors.",
    },
    () => ({
      description: "Open Fleet Ops",
      messages: [{ role: "user" as const, content: { type: "text" as const, text: openFleetOpsPromptText() } }],
    }),
  );

  server.registerPrompt(
    "delayed_vans_today",
    {
      title: "Delayed vans today",
      description: "Analog of “BUs with trade today”: list_delayed_vans + live map.",
    },
    () => ({
      description: "List delayed vans and open the map",
      messages: [
        { role: "user" as const, content: { type: "text" as const, text: delayedVansTodayPromptText() } },
      ],
    }),
  );

  server.registerPrompt(
    "region_ops_report",
    {
      title: "Region ops report",
      description: "Parameterized weekly-style report. Analog of weekly_sales_report(department).",
      argsSchema: { region: regionArg },
    },
    ({ region }) => ({
      description: `Ops report for ${region}`,
      messages: [
        {
          role: "user" as const,
          content: { type: "text" as const, text: regionOpsReportPromptText(region) },
        },
      ],
    }),
  );

  server.registerPrompt(
    "incident_playbook",
    {
      title: "Incident playbook",
      description: "Sheets + confirm/snooze in-app; Claude only for judgment.",
      argsSchema: { vehicle_id: vehicleArg },
    },
    ({ vehicle_id }) => ({
      description: `Incident playbook for ${vehicle_id?.trim() || "open alert"}`,
      messages: [
        {
          role: "user" as const,
          content: { type: "text" as const, text: incidentPlaybookPromptText(vehicle_id) },
        },
      ],
    }),
  );

  server.registerPrompt(
    "open_ops_board",
    {
      title: "Open operations board",
      description: "KPI board with mock query-behind. Not Claude Dashboards product.",
    },
    () => ({
      description: "Operations board walkthrough",
      messages: [
        { role: "user" as const, content: { type: "text" as const, text: openOpsBoardPromptText() } },
      ],
    }),
  );

  server.registerPrompt(
    "fleet_briefing_story",
    {
      title: "Fleet briefing story",
      description: "CSS briefing POC — not Claude Motion / MP4.",
    },
    () => ({
      description: "Fleet briefing narration",
      messages: [
        { role: "user" as const, content: { type: "text" as const, text: fleetBriefingStoryPromptText() } },
      ],
    }),
  );

  server.registerResource(
    "glossary",
    GLOSSARY_URI,
    {
      title: "Fleet glossary",
      description: "Definitions for van, hub, delayed, on-time. Analog of a BU/trade glossary.",
      mimeType: "text/markdown",
    },
    async (uri) => ({
      contents: [{ uri: uri.href, mimeType: "text/markdown", text: GLOSSARY_MD }],
    }),
  );

  server.registerResource(
    "my-regions",
    MY_REGIONS_URI,
    {
      title: "My regions",
      description: "Mock post-auth entitlements (SOMA + Mission). Analog of my territories.",
      mimeType: "text/markdown",
    },
    async (uri) => ({
      contents: [{ uri: uri.href, mimeType: "text/markdown", text: MY_REGIONS_MD }],
    }),
  );

  server.registerResource(
    "dashboard-schema",
    DASHBOARD_SCHEMA_URI,
    {
      title: "Dashboard field guide",
      description: "How to read KPI cards and region rows in the operations dashboard.",
      mimeType: "text/markdown",
    },
    async (uri) => ({
      contents: [{ uri: uri.href, mimeType: "text/markdown", text: DASHBOARD_SCHEMA_MD }],
    }),
  );

  server.registerResource(
    "claude-product-notes",
    CLAUDE_PRODUCT_URI,
    {
      title: "Claude product vs this connector",
      description: "Dashboards/Motion are Claude products — not this MCP server. See CLAUDE_PRODUCT.md.",
      mimeType: "text/markdown",
    },
    async (uri) => ({
      contents: [{ uri: uri.href, mimeType: "text/markdown", text: CLAUDE_PRODUCT_NOTES_MD }],
    }),
  );

  server.registerResource(
    "today-snapshot",
    TODAY_SNAPSHOT_URI,
    {
      title: "Today's fleet snapshot",
      description: "Frozen mocked snapshot. Attach for grounding; tools still own live UI.",
      mimeType: "text/markdown",
    },
    async (uri) => ({
      contents: [{ uri: uri.href, mimeType: "text/markdown", text: todaySnapshotMd() }],
    }),
  );

  server.registerResource(
    "region-briefing",
    new ResourceTemplate(REGION_TEMPLATE, {
      list: async () => ({
        resources: REGIONS.map((region) => ({
          uri: `ops://region/${region}`,
          name: `${region} briefing`,
          title: `${region} region briefing`,
          description: `On-time, volume, incidents, and vans for ${region}`,
          mimeType: "text/markdown",
        })),
      }),
    }),
    {
      title: "Region briefing",
      description: "Per-region briefing. URI ops://region/{region}.",
      mimeType: "text/markdown",
    },
    async (uri, { region }) => ({
      contents: [
        {
          uri: uri.href,
          mimeType: "text/markdown",
          text: regionBriefing(String(region ?? "")),
        },
      ],
    }),
  );
}
