/**
 * MCP Apps exploration server.
 *
 * Pattern from the official MCP Apps build guide:
 * a tool with `_meta.ui.resourceUri` plus a `text/html;profile=mcp-app` resource.
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import {
  registerAppResource,
  registerAppTool,
  RESOURCE_MIME_TYPE,
} from "@modelcontextprotocol/ext-apps/server";
import cors from "cors";
import express from "express";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { FLEET_SNAPSHOT } from "./src/mock-data.ts";

const SERVER_FILE = fileURLToPath(import.meta.url);
const ROOT = path.dirname(SERVER_FILE);
const DIST_DIR = path.join(ROOT, "dist");
const RESOURCE_URI = "ui://mcp-apps-exploration/gallery.html";

const viewSchema = z
  .enum(["overview", "map", "dashboard", "modals", "interact"])
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

  return server;
}

async function serveHttp(port = 3001) {
  const expressApp = express();
  expressApp.use(cors());
  expressApp.use(express.json());
  expressApp.post("/mcp", async (req, res) => {
    const server = createServer();
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
      enableJsonResponse: true,
    });
    res.on("close", () => transport.close());
    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);
  });
  expressApp.listen(port, () => {
    console.log(`MCP Apps exploration listening on http://localhost:${port}/mcp`);
  });
}

async function serveStdio() {
  const server = createServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

const isStdio = process.argv.includes("--stdio");
if (isStdio) {
  await serveStdio();
} else {
  await serveHttp(Number(process.env.PORT ?? 3001));
}
