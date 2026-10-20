/**
 * MCP Apps exploration server.
 *
 * Pattern from the official MCP Apps build guide:
 * a tool with `_meta.ui.resourceUri` plus a `text/html;profile=mcp-app` resource.
 * Prompts and read-only ops:// resources are registered via registerCatalog.
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import {
  registerAppResource,
  registerAppTool,
  RESOURCE_MIME_TYPE,
} from "@modelcontextprotocol/ext-apps/server";
import cors from "cors";
import express from "express";
import type { Server } from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { registerCatalog } from "./src/catalog.ts";
import { registerDomainTools, getLiveSnapshot } from "./src/domain-tools.ts";

const SERVER_FILE = fileURLToPath(import.meta.url);
const ROOT = path.dirname(SERVER_FILE);
const DIST_DIR = path.join(ROOT, "dist");
const RESOURCE_URI = "ui://mcp-apps-exploration/gallery.html";

const viewSchema = z
  .enum(["overview", "map", "dashboard", "motion", "modals", "interact"])
  .optional()
  .describe("Which Fleet Ops surface to open first");

export function createServer(): McpServer {
  const server = new McpServer({
    name: "fleet-ops",
    version: "0.2.0",
  });

  const readHtml = async () => {
    const html = await fs.readFile(path.join(DIST_DIR, "mcp-app.html"), "utf-8");
    return {
      contents: [
        {
          uri: RESOURCE_URI,
          mimeType: RESOURCE_MIME_TYPE,
          text: html,
          _meta: {
            ui: {
              prefersBorder: false,
              csp: {
                // Self-contained canvas map: no tile CDN required.
                // Keep this list if you later swap in MapLibre/Cesium like
                // examples/map-server in modelcontextprotocol/ext-apps.
                connectDomains: [],
                resourceDomains: [],
              },
            },
          },
        },
      ],
    };
  };

  registerAppResource(
    server,
    RESOURCE_URI,
    RESOURCE_URI,
    { mimeType: RESOURCE_MIME_TYPE },
    readHtml,
  );

  type FleetView = NonNullable<z.infer<typeof viewSchema>>;

  const payloadFor = (view?: FleetView) => ({
    ...getLiveSnapshot(),
    view: view ?? "overview",
  });

  const openView = (view: FleetView) => ({
    content: [{ type: "text" as const, text: JSON.stringify({ view }) }],
    structuredContent: payloadFor(view),
  });

  const registerViewTool = (
    name: string,
    title: string,
    description: string,
    view: FleetView,
  ) => {
    registerAppTool(
      server,
      name,
      { title, description, _meta: { ui: { resourceUri: RESOURCE_URI } } },
      async () => openView(view),
    );
  };

  // UI tools (open MCP App). Domain data tools live in registerDomainTools.
  registerAppTool(
    server,
    "open_fleet_ops",
    {
      title: "Open Fleet Ops",
      description:
        "Territory Trade–style connector home: host inspector, live map, ops board, sheets, and filters. Prefer this when the user wants the Fleet Ops app.",
      inputSchema: { view: viewSchema },
      _meta: { ui: { resourceUri: RESOURCE_URI } },
    },
    async ({ view }) => {
      const payload = payloadFor(view);
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ view: payload.view, city: payload.city, vans: payload.vehicles.length }),
          },
        ],
        structuredContent: payload,
      };
    },
  );

  // Backward-compatible alias for older prompts / chats.
  registerAppTool(
    server,
    "explore_mcp_apps",
    {
      title: "Open Fleet Ops (alias)",
      description: "Alias for open_fleet_ops. Prefer open_fleet_ops.",
      inputSchema: { view: viewSchema },
      _meta: { ui: { resourceUri: RESOURCE_URI } },
    },
    async ({ view }) => {
      const payload = payloadFor(view);
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ view: payload.view, city: payload.city, vans: payload.vehicles.length }),
          },
        ],
        structuredContent: payload,
      };
    },
  );

  registerViewTool(
    "show_live_map",
    "Show live fleet map",
    "Open the live map of mocked delivery vans. Pan, zoom, filter, inspect — no Claude turn for map chrome.",
    "map",
  );
  registerViewTool(
    "show_operations_dashboard",
    "Show operations board",
    "Ops KPI board with mock query-behind-number. Refresh/filter via callServerTool; Explain only for Claude judgment.",
    "dashboard",
  );
  registerViewTool(
    "show_sheet_patterns",
    "Show incident sheets",
    "Bottom sheets and confirm dialogs for incident playbook. Confirm/snooze stay in-app; judgment uses chat.",
    "modals",
  );
  registerViewTool(
    "show_fleet_briefing",
    "Show fleet briefing animation",
    "CSS briefing scene (POC only — not Claude Motion / MP4). See CLAUDE_PRODUCT.md.",
    "motion",
  );
  registerViewTool(
    "show_fleet_motion",
    "Show fleet briefing (alias)",
    "Alias for show_fleet_briefing. Not Claude Motion.",
    "motion",
  );
  registerViewTool(
    "show_interaction_controls",
    "Show fleet filters",
    "Segmented filters and SLA slider. Apply uses callServerTool; Ask Claude is judgment-only.",
    "interact",
  );

  registerDomainTools(server);
  registerCatalog(server);
  return server;
}

async function attachMcp(req: express.Request, res: express.Response) {
  const server = createServer();
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: undefined,
    enableJsonResponse: true,
  });
  res.on("close", () => transport.close());
  await server.connect(transport);
  await transport.handleRequest(req, res, req.body);
}

export async function startHttpServer(
  port = Number(process.env.PORT ?? 3001),
  host = process.env.HOST ?? "0.0.0.0",
): Promise<{ port: number; host: string; close: () => Promise<void> }> {
  const expressApp = express();
  expressApp.use(cors());
  expressApp.use(express.json());

  expressApp.get("/", (_req, res) => {
    res.json({
      name: "fleet-ops",
      role: "Territory Trade–style MCP Apps connector (mocked SF fleet)",
      product_vs_mcp: "See CLAUDE_PRODUCT.md — Claude Dashboards/Motion are not this server.",
      transport: "streamable-http",
      mcp: "/mcp",
    });
  });

  expressApp.get("/health", (_req, res) => {
    res.json({
      ok: true,
      transport: "http",
      connector: "fleet-ops",
      prompts: [
        "delayed_vans_today",
        "fleet_briefing_story",
        "incident_playbook",
        "open_fleet_ops",
        "open_ops_board",
        "region_ops_report",
      ],
      ui_tools: [
        "open_fleet_ops",
        "show_live_map",
        "show_operations_dashboard",
        "show_fleet_briefing",
        "show_sheet_patterns",
        "show_interaction_controls",
      ],
      domain_tools: [
        "list_delayed_vans",
        "refresh_fleet_snapshot",
        "filter_fleet",
        "get_vehicle_detail",
        "get_region_summary",
      ],
      resources: [
        "ops://glossary",
        "ops://my-regions",
        "ops://dashboard-schema",
        "ops://claude-product-notes",
        "ops://snapshot/today",
        "ops://region/{region}",
        "ui://mcp-apps-exploration/gallery.html",
      ],
    });
  });

  expressApp.all("/mcp", async (req, res) => {
    try {
      await attachMcp(req, res);
    } catch (error) {
      console.error("MCP request failed", error);
      if (!res.headersSent) {
        res.status(500).json({
          jsonrpc: "2.0",
          error: { code: -32603, message: "Internal server error" },
          id: null,
        });
      }
    }
  });

  const httpServer = await new Promise<Server>((resolve) => {
    const listener = expressApp.listen(port, host, () => resolve(listener));
  });
  const address = httpServer.address();
  const boundPort =
    address && typeof address === "object" ? address.port : port;

  console.log(`MCP Apps exploration listening on http://${host}:${boundPort}/mcp`);

  return {
    port: boundPort,
    host,
    close: () =>
      new Promise((resolve, reject) => {
        httpServer.close((err) => (err ? reject(err) : resolve()));
      }),
  };
}

const isMain =
  process.argv[1] !== undefined &&
  path.resolve(process.argv[1]) === SERVER_FILE;

if (isMain) {
  await startHttpServer();
}
