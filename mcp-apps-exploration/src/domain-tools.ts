/**
 * Non-UI domain tools for Fleet Ops (Territory Trade analog).
 * Callable from Claude chat *or* from the MCP App via callServerTool —
 * no new model turn required for filter / refresh / drill-down.
 */
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { REGIONS } from "./catalog.ts";
import {
  delayedVansTableMarkdown,
  filterFleet,
  listDelayedVans,
  refreshFleetSnapshot,
  vehicleDetail,
} from "./fleet-ops.ts";
import { FLEET_SNAPSHOT, type VehicleStatus } from "./mock-data.ts";

const statusEnum = z.enum(["all", "en_route", "idle", "delayed", "charging"]);
const regionEnum = z.enum(["all", "SOMA", "Mission", "Marina", "Sunset", "Richmond"]);

let liveSnapshot = { ...FLEET_SNAPSHOT };

export function getLiveSnapshot() {
  return liveSnapshot;
}

export function registerDomainTools(server: McpServer): void {
  server.registerTool(
    "list_delayed_vans",
    {
      title: "List delayed vans (trade today)",
      description:
        "Territory Trade analog of “BUs with trade today”: return delayed/critical vans as a Markdown table. Does not open UI — pair with show_live_map if needed.",
      inputSchema: {},
    },
    async () => {
      const vans = listDelayedVans(liveSnapshot);
      const table = delayedVansTableMarkdown(liveSnapshot);
      return {
        content: [{ type: "text" as const, text: table }],
        structuredContent: { vans, generatedAt: liveSnapshot.generatedAt },
      };
    },
  );

  server.registerTool(
    "refresh_fleet_snapshot",
    {
      title: "Refresh fleet snapshot",
      description:
        "Mock live refresh of KPIs and ETAs. Safe to call from the MCP App via callServerTool (no Claude turn).",
      inputSchema: {},
    },
    async () => {
      liveSnapshot = refreshFleetSnapshot(liveSnapshot);
      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify({
              generatedAt: liveSnapshot.generatedAt,
              onTime: liveSnapshot.kpis.find((k) => k.id === "ontime")?.value,
            }),
          },
        ],
        // No view override — keep the app on whatever surface called refresh.
        structuredContent: { ...liveSnapshot },
      };
    },
  );

  server.registerTool(
    "filter_fleet",
    {
      title: "Filter fleet",
      description:
        "Filter vans by status and/or region desk. Prefer callServerTool from the app for instant UI updates.",
      inputSchema: {
        status: statusEnum.optional().describe("Vehicle status or all"),
        region: regionEnum.optional().describe("Region desk or all"),
        sla_target: z.number().min(80).max(99).optional().describe("Flag regions below this on-time %"),
        view: z.enum(["map", "dashboard", "overview", "interact"]).optional(),
      },
    },
    async ({ status, region, sla_target, view }) => {
      const filtered = filterFleet(liveSnapshot, {
        status: (status ?? "all") as VehicleStatus | "all",
        region: region ?? "all",
        slaTarget: sla_target,
      });
      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify({
              status: status ?? "all",
              region: region ?? "all",
              vans: filtered.vehicles.length,
              alerts: filtered.alerts.length,
            }),
          },
        ],
        structuredContent: { ...filtered, view: view ?? "map" },
      };
    },
  );

  server.registerTool(
    "get_vehicle_detail",
    {
      title: "Get vehicle detail",
      description: "Drill into one van (region, alerts, site hint). Use from app or chat.",
      inputSchema: {
        vehicle_id: z.string().describe("Van id such as VAN-07"),
      },
    },
    async ({ vehicle_id }) => {
      const detail = vehicleDetail(vehicle_id, liveSnapshot);
      return {
        content: [{ type: "text" as const, text: JSON.stringify(detail, null, 2) }],
        structuredContent: {
          focusVehicleId: vehicle_id,
          vehicleDetail: detail,
        },
      };
    },
  );

  server.registerTool(
    "get_region_summary",
    {
      title: "Get region summary",
      description: "On-time, volume, incidents for one region desk (Territory Trade department analog).",
      inputSchema: {
        region: z.enum(REGIONS),
      },
    },
    async ({ region }) => {
      const row = liveSnapshot.regions.find((r) => r.region === region);
      const filtered = filterFleet(liveSnapshot, { region });
      return {
        content: [
          {
            type: "text" as const,
            text: row
              ? `**${region}**: ${row.onTimePct}% on-time, ${row.volume} stops, ${row.incidents} incidents.`
              : `Unknown region ${region}`,
          },
        ],
        structuredContent: { ...filtered, view: "dashboard", focusRegion: region },
      };
    },
  );
}
