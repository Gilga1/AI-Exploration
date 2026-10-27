# Claude Artifacts exploration

Length-and-breadth research of **Claude Artifacts** (what is possible, what is not), plus a runnable **Fleet Ops Artifact Lab** that uses mock fleet data but the **real Artifact API shapes** (`window.claude.complete`, proxied Messages `fetch`, `window.storage`, interactions, transitions, event-driven updates).

This is **not** an MCP App. For MCP Apps see `feature/mcp-apps-exploration`.

## Docs

| File | Contents |
| --- | --- |
| [`RESEARCH.md`](./RESEARCH.md) | Capabilities, limits, follow-up context, APIs, storage, CSP |
| [`COMPARISON.md`](./COMPARISON.md) | Artifacts vs MCP Apps |

## Local preview

```bash
cd claude-artifacts-exploration
npm install
npm test
npm run preview
```

Open the URL Vite prints (default `http://localhost:4178/preview/index.html`). The preview host injects [`preview/mock-bridge.js`](./preview/mock-bridge.js) so `window.claude` / `window.storage` / Anthropic Messages `fetch` work offline.

## Artifact source

[`artifacts/fleet-ops-lab.html`](./artifacts/fleet-ops-lab.html) — single-file page you can also paste into Claude as an artifact. Tabs:

1. **Overview** — mock KPIs  
2. **Interactions** — filters, row select, tooltips, drag triage board, copy-as-chat-prompt  
3. **Transitions** — live duration / delay / easing  
4. **Follow-up API** — multi-turn history via `complete()` and Messages `fetch`  
5. **Dynamic events** — refresh + interval + Claude on event  
6. **Storage** — personal / shared KV  

Deep links: `#overview`, `#interactions`, `#transitions`, `#followup`, `#events`, `#storage`.

## Try inside Claude

1. Open claude.ai (Pro+ for storage / AI-powered artifacts as applicable).  
2. Ask Claude to create an artifact from `artifacts/fleet-ops-lab.html`, or paste the file.  
3. Enable Artifacts that use Claude when prompted.  
4. Exercise Follow-up API and Storage on the **published** link if storage no-ops in draft (legacy behavior).

## Honest limits of this repo

- Mock data only — no live Salesforce / warehouse.  
- Local bridge is a **simulator**, not Anthropic’s inject script.  
- We did not attach to production Claude in this Cloud Agent environment.  
- Product details can drift; Prefer Help Center when conflicting.
