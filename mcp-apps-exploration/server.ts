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
import { FLEET_SNAPSHOT } from "./src/mock-data.ts";

const SERVER_FILE = fileURLToPath(import.meta.url);
const ROOT = path.dirname(SERVER_FILE);
const DIST_DIR = path.join(ROOT, "dist");
const RESOURCE_URI = "ui://mcp-apps-exploration/gallery.html";

const viewSchema = z
  .enum(["overview", "map", "dashboard", "motion", "modals", "interact"])
  .optional()
  .describe("Which gallery surface to open first");

export function createServer(): McpServer {
  const server = new McpServer({
    name: "mcp-apps-exploration",
    version: "0.1.0",
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

  const payloadFor = (view: z.infer<typeof viewSchema>) => ({
    ...FLEET_SNAPSHOT,
    view: view ?? "overview",
  });

  registerAppTool(
    server,
    "explore_mcp_apps",
    {
      title: "Explore MCP Apps UX",
      description:
        "Open the MCP Apps gallery: host-size inspector, live fleet map, dashboard, sheets/modals, and interaction controls. Use this whenever the user wants to see rich UI inside Claude.",
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

  registerAppTool(
    server,
    "show_live_map",
    {
      title: "Show live fleet map",
      description: "Render an interactive live map of mocked delivery vans. Pan, zoom, and inspect vehicles.",
      _meta: { ui: { resourceUri: RESOURCE_URI } },
    },
    async () => ({
      content: [{ type: "text", text: JSON.stringify({ view: "map" }) }],
      structuredContent: payloadFor("map"),
    }),
  );

  registerAppTool(
    server,
    "show_operations_dashboard",
    {
      title: "Show operations dashboard",
      description: "Render KPI cards, hourly volume, regional meters, and incident cards from mocked ops data.",
      _meta: { ui: { resourceUri: RESOURCE_URI } },
    },
    async () => ({
      content: [{ type: "text", text: JSON.stringify({ view: "dashboard" }) }],
      structuredContent: payloadFor("dashboard"),
    }),
  );

  registerAppTool(
    server,
    "show_sheet_patterns",
    {
      title: "Show modal and sheet patterns",
      description: "Demonstrate bottom sheets, in-iframe dialogs, and handing decisions back to Claude via ui/message.",
      _meta: { ui: { resourceUri: RESOURCE_URI } },
    },
    async () => ({
      content: [{ type: "text", text: JSON.stringify({ view: "modals" }) }],
      structuredContent: payloadFor("modals"),
    }),
  );

  registerAppTool(
    server,
    "show_fleet_motion",
    {
      title: "Show fleet motion explainer",
      description:
        "Claude Motion-style: code-built animation summarizing on-time %, delays, and critical holds (mock data).",
      _meta: { ui: { resourceUri: RESOURCE_URI } },
    },
    async () => ({
      content: [{ type: "text", text: JSON.stringify({ view: "motion" }) }],
      structuredContent: payloadFor("motion"),
    }),
  );

  registerAppTool(
    server,
    "show_interaction_controls",
    {
      title: "Show interaction controls",
      description: "Segmented filters, sliders, toggles, carousel, model-context updates, and chat handoff.",
      _meta: { ui: { resourceUri: RESOURCE_URI } },
    },
    async () => ({
      content: [{ type: "text", text: JSON.stringify({ view: "interact" }) }],
      structuredContent: payloadFor("interact"),
    }),
  );

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
      name: "mcp-apps-exploration",
      transport: "streamable-http",
      mcp: "/mcp",
    });
  });

  expressApp.get("/health", (_req, res) => {
    res.json({
      ok: true,
      transport: "http",
      prompts: [
        "animate_fleet_briefing",
        "delayed_vans_today",
        "incident_playbook",
        "open_gallery",
        "open_ops_dashboard",
        "region_ops_report",
      ],
      resources: [
        "ops://glossary",
        "ops://my-regions",
        "ops://dashboard-schema",
        "ops://claude-artifacts-guide",
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
