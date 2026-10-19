# MCP Apps exploration

Interactive MCP Apps gallery for **Claude** (and any MCP Apps host): live maps, dashboards, sheets/modals, and host-controlled layout.

This is an experiment with **mocked ops data**. It exists to answer two questions:

1. What rich UX is actually in-scope for MCP Apps?
2. Is Claude’s chat column a hard width limit? **No.** Inline width is host-controlled; fullscreen is a first-class mode.

## Challenge the width screenshot

The attached Claude screenshot is the **conversation column**, which is how Claude hosts **inline** apps. It is not the MCP Apps maximum.

Evidence in this repo:

- `src/host-context.ts` quotes the spec type: hosts send `containerDimensions.width` **or** `maxWidth`, plus `displayMode: "inline" | "fullscreen" | "pip"`.
- `src/ui/styles.css` sizes the app at `width: 100%` — never `736px`.
- The local host at `preview/index.html` mounts the same iframe at 320 / 560 / 736 / 960 / 1200 / 100% / fullscreen / PiP.
- Claude Desktop has been **observed** at inline `width: 736`, `maxHeight: 5000`, modes `inline` + `fullscreen` ([ext-apps#688](https://github.com/modelcontextprotocol/ext-apps/issues/688)). That is a host choice. The spec initialize example even uses `width: 400`.
- Official Claude design guidelines: apps always fill container width, design from **320px to fullscreen**, and request `ui/request-display-mode` for immersive work.

PiP is in the SDK. Claude.ai currently does not advertise it and silently stays inline ([anthropics/claude-ai-mcp#60](https://github.com/anthropics/claude-ai-mcp/issues/60)).

## Run the layout lab (no Claude required)

```bash
cd mcp-apps-exploration
npm install
npm test
npm run preview
```

Open `http://localhost:4177/preview/index.html`. Change the width preset and display mode. The pill in the app should track the host’s reported width.

## Run as an MCP server for Claude

This server speaks **Streamable HTTP only** (no stdio). Claude loads the app HTML from `POST /mcp`; you do not host a separate frontend.

```bash
npm run build
npm run serve          # http://127.0.0.1:3001/mcp
```

Health check: `GET http://127.0.0.1:3001/health`

**Claude.ai:** tunnel `http://127.0.0.1:3001/mcp` (Cloudflare Tunnel, ngrok) and add a custom connector (paid plans).

**Claude Code:**

```bash
claude mcp add --transport http mcp-apps-exploration http://127.0.0.1:3001/mcp
```

or in `.mcp.json`:

```json
{
  "mcpServers": {
    "mcp-apps-exploration": {
      "type": "http",
      "url": "http://127.0.0.1:3001/mcp"
    }
  }
}
```

**Claude Desktop:** Desktop’s JSON config still only launches stdio processes. Point it at this HTTP server with a bridge, or add the public tunnel as a custom connector:

```json
{
  "mcpServers": {
    "mcp-apps-exploration": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://127.0.0.1:3001/mcp", "--transport", "http-only"]
    }
  }
}
```

Then ask: “Open the MCP Apps gallery” or “Show the live fleet map”.

## Prompts and resources (test in Claude)

After the connector is connected, Claude does **not** auto-run these. Open a chat, click **+** (bottom-left of the composer) → **Connectors** → **Add from mcp-apps-exploration**.

### Prompts (named recipes)

| Prompt | Args | What Claude should do |
| --- | --- | --- |
| `open_gallery` | — | Call `explore_mcp_apps` |
| `delayed_vans_today` | — | Analog of “BUs with trade today”: call `show_live_map`, table delayed vans |
| `region_ops_report` | `region` | Analog of `weekly_sales_report(department)`: call dashboard, compare regions |
| `incident_playbook` | optional `vehicle_id` | Open sheets view and walk an alert |
| `open_ops_dashboard` | — | [Claude Dashboards](https://claude.com/resources/articles/dashboards-and-motion)-style KPI walkthrough |
| `animate_fleet_briefing` | — | [Claude Motion](https://claude.com/resources/articles/dashboards-and-motion)-style code animation |

**Instant run:** On the gallery **Overview** tab, **Run now** sends the same text via `ui/message` (no extra “go” step). The + menu still works for attaching resources.

Claude Desktop often attaches the prompt as a **file pill** when picked from +; in-app buttons skip that step.

### Resources (read-only context)

| URI | Role |
| --- | --- |
| `ops://glossary` | Term definitions (van ≈ BU, delayed ≈ trade today) |
| `ops://my-regions` | Mock post-auth entitlements (SOMA + Mission) |
| `ops://dashboard-schema` | How to read KPI fields |
| `ops://snapshot/today` | Frozen fleet table — not a live query |
| `ops://claude-artifacts-guide` | How this POC maps to Claude Dashboards & Motion |
| `ops://region/{region}` | Per-region briefing template |
| `ui://mcp-apps-exploration/gallery.html` | MCP App HTML (host-loaded, not for the + menu) |

**Suggested Claude trial:** attach `ops://glossary` + pick `delayed_vans_today` → send `go`. You want the live map app **and** a Markdown table that uses glossary labels.

App buttons still use `callServerTool` / `sendMessage`. They do not invoke `prompts/get`.

## Tools

| Tool | UI |
| --- | --- |
| `explore_mcp_apps` | Overview + host inspector |
| `show_live_map` | Canvas live fleet map |
| `show_operations_dashboard` | KPIs, charts, alerts — click any section, then **Explain** (`ui/message`) |
| `show_fleet_motion` | CSS motion explainer (Claude Motion pattern) |
| `show_sheet_patterns` | Bottom sheet + dialog + chat handoff |
| `show_interaction_controls` | Segmented, slider, toggles, carousel |

**Dashboard Explain:** The app calls `sendMessage` on button click (with selection staged via `updateModelContext`). On **claude.ai** the host may still place text in the composer and require you to press Send ([anthropics/claude-ai-mcp#1111](https://github.com/anthropics/claude-ai-mcp/issues/1111)); Claude Desktop typically starts the turn immediately.

## Honest limits (Claude)

- Sandboxed iframe, deny-by-default CSP. Third-party map tiles need `_meta.ui.csp`.
- `frameDomains` (nested third-party iframes) is restricted in Claude.
- Inline: auto-fit height, avoid nested vertical scroll; host owns vertical pan.
- Prefer visible controls over menus; prefer sheets over floating dialogs.
- Camera / mic / geolocation on mobile WebView: not available.
- All UI↔host calls are auditable JSON-RPC. The app cannot see Claude’s DOM.

See `RESEARCH.md` for the full map of capabilities.
