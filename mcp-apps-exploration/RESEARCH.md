# MCP Apps: what is actually possible

Research snapshot for experimenting with MCP Apps inside Claude. Grounded in the 2026-01-26 spec, the `@modelcontextprotocol/ext-apps` SDK, and Claude’s published design/getting-started docs — not in the chat-column screenshot.

## Sources

- Spec: [SEP-1865](https://modelcontextprotocol.io/seps/1865-mcp-apps-interactive-user-interfaces-for-mcp) and [ext-apps `src/spec.types.ts`](https://github.com/modelcontextprotocol/ext-apps/blob/main/src/spec.types.ts)
- Build guide: https://modelcontextprotocol.io/extensions/apps/build
- Overview: https://modelcontextprotocol.io/extensions/apps/overview
- Claude design guidelines: https://claude.com/docs/connectors/building/mcp-apps/design-guidelines
- Claude getting started: https://claude.com/docs/connectors/building/mcp-apps/getting-started
- Official examples: Cesium globe (`map-server`), Three.js, ShaderToy, PDF, sheet music, cohort heatmap, budget allocator, system monitor
- Host observations: [ext-apps#688](https://github.com/modelcontextprotocol/ext-apps/issues/688), [ext-apps#502](https://github.com/modelcontextprotocol/ext-apps/issues/502), [claude-ai-mcp#60](https://github.com/anthropics/claude-ai-mcp/issues/60)

## Architecture (one sentence)

A tool declares `_meta.ui.resourceUri` → host reads a `ui://` resource with MIME `text/html;profile=mcp-app` → HTML runs in a **sandboxed iframe** → View and Host speak JSON-RPC over `postMessage`.

## Display and size (the width question)

The protocol type is explicit (`McpUiHostContext` in `spec.types.ts`):

- `displayMode`: `"inline" | "fullscreen" | "pip"`
- `availableDisplayModes`: what **this host** will honor
- `containerDimensions`: **either** fixed `width` **or** `maxWidth`, and **either** fixed `height` **or** `maxHeight`

Claude design guidelines: apps **always fill the container width**, no fixed breakpoints, design from **320px up to fullscreen**, use container queries and `hostContext`. Inline cards auto-fit height and must not nest-scroll. Fullscreen is the mode for dashboards, maps, and editors. The composer stays visible; honor `safeAreaInsets`.

Observed Claude Desktop inline (issue 688): `width: 736`, `maxHeight: 5000`, modes `inline` + `fullscreen`. That is a host layout choice, identical in kind to the spec’s example of `width: 400, maxHeight: 600`. Requesting `pip` on claude.ai currently comes back as `inline`.

So: the red box in the screenshot is Claude’s **inline chat surface**. It is not “MCP Apps can only be this wide.” Fullscreen is specified, implemented in the SDK (`App.requestDisplayMode`), and recommended by Claude for exactly the experiences in this gallery.

## Bidirectional API (View → Host)

From `App` in ext-apps:

| Method | Wire | Use |
| --- | --- | --- |
| `connect()` | `ui/initialize` | Handshake; receives hostContext |
| `callServerTool` | `tools/call` | Refresh data without a new chat turn |
| `readServerResource` / `listServerResources` | resources | Extra payloads |
| `sendMessage` | `ui/message` | Inject a user message into chat |
| `updateModelContext` | `ui/update-model-context` | Silent context for the next turn |
| `openLink` | `ui/open-link` | Host-mediated navigation (`window.open` is sandboxed) |
| `downloadFile` | `ui/download-file` | Host-mediated download |
| `requestDisplayMode` | `ui/request-display-mode` | inline / fullscreen / pip |
| `sendSizeChanged` | `ui/notifications/size-changed` | autoResize default |
| `createSamplingMessage` | `sampling/createMessage` | Host LLM, if advertised |
| `registerTool` | app-side tools | Host can call into the widget |
| `requestTeardown` | `ui/notifications/request-teardown` | Ask to unmount |

Host → View: `tool-input`, `tool-input-partial` (streaming args), `tool-result`, `tool-cancelled`, `host-context-changed`.

## Security and CSP

- Default: no network, no parent DOM, no cookies, no popups.
- Declare origins in resource `_meta.ui.csp`: `connectDomains`, `resourceDomains`, `baseUriDomains`.
- Claude: `frameDomains` (embed third-party iframes) **restricted pending security review**.
- Permissions metadata can request camera / mic / clipboard; mobile Claude WebView currently grants none of camera, mic, or location.
- For Claude web, set `_meta.ui.domain` to `sha256(serverUrl)[0:32].claudemcpcontent.com`.

This gallery’s map is a **self-contained canvas** so it works with empty CSP. Official `map-server` shows the other path: Cesium + OSM tiles via `connectDomains` / `resourceDomains`.

## Claude UX guidelines vs. “cool” widgets

| Pattern | Verdict in Claude |
| --- | --- |
| Live map with pan/zoom | Yes. Horizontal gestures work inline; tall/scroll maps should go fullscreen. Official Cesium example. |
| Dashboard / charts | Yes, especially fullscreen. |
| Segmented controls, sliders, toggles, carousels | Yes — preferred over menus. |
| Bottom sheet inside the iframe | Yes — grows height, plays with autoResize. |
| Floating modal / popover | Possible inside the iframe, **discouraged**: clipping, z-index, composer overlay. |
| Nested vertical scroll inline | No — host owns vertical pan and caps height. |
| Chat input inside the app | No — use `ui/message`. |
| 3D, shaders, PDF, audio | Yes — first-party examples exist. |
| Realtime updates | Yes — keep the iframe, `callServerTool` or push new tool results. |

## Hosts that render MCP Apps

Claude, Claude Desktop, VS Code GitHub Copilot, Microsoft 365 Copilot, Goose, Postman, MCPJam, Archestra.AI (per overview; always re-check the client matrix).

## What we are not claiming

We did not attach this server to production Claude in this environment. The local preview host implements the same `ui/initialize` / `ui/request-display-mode` / `containerDimensions` contract so layout can be proven without Claude. The MCP process is Streamable HTTP (`POST /mcp`); Claude.ai uses a public tunnel as a custom connector, Claude Code uses `"type": "http"`, and Claude Desktop can reach the same endpoint through `mcp-remote` or a custom connector.
