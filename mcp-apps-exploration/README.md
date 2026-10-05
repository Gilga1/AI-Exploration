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

```bash
npm run build
npm run serve          # Streamable HTTP at http://localhost:3001/mcp
npm run serve:stdio    # for Claude Desktop
```

Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcp-apps-exploration": {
      "command": "npx",
      "args": ["tsx", "/ABS/PATH/ai-exploration/mcp-apps-exploration/server.ts", "--stdio"]
    }
  }
}
```

Claude web: tunnel `http://localhost:3001` and add a custom connector (paid plans). Then ask: “Open the MCP Apps gallery” or “Show the live fleet map”.

## Tools

| Tool | UI |
| --- | --- |
| `explore_mcp_apps` | Overview + host inspector |
| `show_live_map` | Canvas live fleet map |
| `show_operations_dashboard` | KPIs, charts, alerts |
| `show_sheet_patterns` | Bottom sheet + dialog + chat handoff |
| `show_interaction_controls` | Segmented, slider, toggles, carousel |

## Honest limits (Claude)

- Sandboxed iframe, deny-by-default CSP. Third-party map tiles need `_meta.ui.csp`.
- `frameDomains` (nested third-party iframes) is restricted in Claude.
- Inline: auto-fit height, avoid nested vertical scroll; host owns vertical pan.
- Prefer visible controls over menus; prefer sheets over floating dialogs.
- Camera / mic / geolocation on mobile WebView: not available.
- All UI↔host calls are auditable JSON-RPC. The app cannot see Claude’s DOM.

See `RESEARCH.md` for the full map of capabilities.
