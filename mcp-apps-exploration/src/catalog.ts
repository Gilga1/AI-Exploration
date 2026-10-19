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
import { FLEET_SNAPSHOT, type RegionRow } from "./mock-data.ts";
import {
  animateFleetBriefingPromptText,
  delayedVansTodayPromptText,
  incidentPlaybookPromptText,
  openGalleryPromptText,
  openOpsDashboardPromptText,
  regionOpsReportPromptText,
} from "./prompt-copy.ts";

export const REGIONS = ["SOMA", "Mission", "Marina", "Sunset", "Richmond"] as const;
export type RegionName = (typeof REGIONS)[number];

export const GLOSSARY_URI = "ops://glossary";
export const MY_REGIONS_URI = "ops://my-regions";
export const DASHBOARD_SCHEMA_URI = "ops://dashboard-schema";
export const TODAY_SNAPSHOT_URI = "ops://snapshot/today";
export const CLAUDE_ARTIFACTS_URI = "ops://claude-artifacts-guide";
export const REGION_TEMPLATE = "ops://region/{region}";

export const CLAUDE_ARTIFACTS_GUIDE_MD = `# Claude Dashboards & Motion (product notes)

This gallery mocks patterns from [Claude Dashboards and Motion](https://claude.com/resources/articles/dashboards-and-motion):

| Product | What it does | How we simulate it here |
| --- | --- | --- |
| **Claude Dashboards** | Connect data platforms; ask in plain language; click a number to see the query; charts stay current. | \`show_operations_dashboard\` + KPI click → mock SQL in the app + \`sendMessage\` to explain. |
| **Claude Motion** | Code-built animations (not video gen); export MP4 from Claude. | \`show_fleet_motion\` CSS scene + “rewrite explainer” hands off to chat. |
| **Docs / Slides / Design** | Artifacts in chat. | Overview + sheets patterns; resources for grounding. |

Enterprise: Dashboards and Motion may be off by default in Organization settings → Artifacts.
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
  const vans = FLEET_SNAPSHOT.vehicles.filter((v) => regionOwnsVan(row, v.id));
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

function regionOwnsVan(row: RegionRow, vanId: string): boolean {
  if (row.region === "Mission") return vanId === "VAN-07" || vanId === "VAN-03";
  if (row.region === "SOMA") return vanId === "VAN-14" || vanId === "VAN-22";
  if (row.region === "Marina") return vanId === "VAN-31";
  if (row.region === "Sunset") return vanId === "VAN-19";
  return false;
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
    "open_gallery",
    {
      title: "Open MCP Apps gallery",
      description:
        "Starter: open the interactive gallery (map, dashboard, sheets). Pick from Claude + → Connectors.",
    },
    () => ({
      description: "Open the MCP Apps gallery",
      messages: [{ role: "user" as const, content: { type: "text" as const, text: openGalleryPromptText() } }],
    }),
  );

  server.registerPrompt(
    "delayed_vans_today",
    {
      title: "Delayed vans today",
      description:
        "Analog of “BUs with trade today”: list delayed/critical vans and open the live map.",
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
      description:
        "Parameterized weekly-style report for one region. Analog of weekly_sales_report(department).",
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
      description: "Walk a delayed van or dock hold with sheets + a chat handoff.",
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
    "open_ops_dashboard",
    {
      title: "Claude Dashboard-style ops board",
      description: "Open the KPI dashboard and explain mock queries behind each metric.",
    },
    () => ({
      description: "Operations dashboard with query transparency",
      messages: [
        { role: "user" as const, content: { type: "text" as const, text: openOpsDashboardPromptText() } },
      ],
    }),
  );

  server.registerPrompt(
    "animate_fleet_briefing",
    {
      title: "Claude Motion-style fleet explainer",
      description: "Open the motion view and narrate a 30-second fleet briefing.",
    },
    () => ({
      description: "Animated fleet explainer",
      messages: [
        { role: "user" as const, content: { type: "text" as const, text: animateFleetBriefingPromptText() } },
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
    "claude-artifacts-guide",
    CLAUDE_ARTIFACTS_URI,
    {
      title: "Claude Dashboards & Motion guide",
      description: "How this POC maps to Claude Dashboards, Motion, and artifact settings.",
      mimeType: "text/markdown",
    },
    async (uri) => ({
      contents: [{ uri: uri.href, mimeType: "text/markdown", text: CLAUDE_ARTIFACTS_GUIDE_MD }],
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
