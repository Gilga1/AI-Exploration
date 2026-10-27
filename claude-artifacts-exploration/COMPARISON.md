# Claude Artifacts vs MCP Apps

Both render interactive UI next to Claude. They are **not** the same protocol.

| Dimension | Claude Artifacts | MCP Apps (`ext-apps`) |
| --- | --- | --- |
| Who authors the UI | Claude (or you via Claude) in chat / Code | You ship an MCP server + `ui://` HTML resource |
| Wire protocol | Injected bridge (`window.claude`, `window.storage`, patched `fetch`) | JSON-RPC over `postMessage` (`ui/initialize`, `tools/call`, …) |
| Talk to host chat | Indirect (paste, comments, Send to Claude) | `sendMessage` / `updateModelContext` |
| Refresh data without a model turn | In-page state, storage, connector calls, or your own Claude calls | `callServerTool` / new tool results |
| Layout modes | Side panel / full artifact URL | `inline` / `fullscreen` / `pip` via `requestDisplayMode` |
| Claude from the UI | First-class (`complete` / Messages proxy) | Via host sampling if advertised, or your backend |
| Persistence | `window.storage` (plan-gated) | Your server / declared CSP domains |
| Best for | Shareable prototypes, docs/slides/design, one-off tools | Production connectors with tools, prompts, resources |

This folder explores **Artifacts only**. For MCP Apps, use `mcp-apps-exploration/` on `feature/mcp-apps-exploration`.
