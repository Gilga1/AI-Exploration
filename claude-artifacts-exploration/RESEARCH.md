# Claude Artifacts: length and breadth

Research snapshot for experimenting with **Claude Artifacts** (claude.ai / Claude Desktop / Claude Code), not MCP Apps. Grounded in Anthropic Help Center + product posts, Claude Code docs, and reverse-engineering notes from live sessions (Simon Willison, community packages that snapshot the inject bridge). Claude’s product surface moves quickly — treat Help Center as authoritative when this file and the product diverge.

**Sibling work:** MCP Apps live under `feature/mcp-apps-exploration` (`mcp-apps-exploration/`). Artifacts and MCP Apps are different sandboxes with different APIs. See [`COMPARISON.md`](./COMPARISON.md).

## Sources

| Kind | URL |
| --- | --- |
| Help Center — what artifacts are | https://support.claude.com/en/articles/17153992-what-are-artifacts-and-how-do-i-use-them |
| Product — Claude-powered artifacts | https://claude.com/resources/articles/claude-powered-artifacts |
| Product — Artifacts feature page | https://claude.com/features/artifacts |
| Claude Code — publish session output | https://code.claude.com/docs/en/artifacts |
| Reverse eng — `window.claude.complete` | https://simonwillison.net/2025/Jun/25/ai-powered-apps-with-claude/ |
| Reverse eng — proxied Messages API | https://simonwillison.net/2025/Jul/31/updates-to-claude/ |
| Community types for inject bridge | https://www.npmjs.com/package/@alistigo/claude-artifact-api |
| Storage deep-dive (cites Help Center) | https://homespun.dev/guides/can-claude-artifacts-store-data |

## Architecture (one sentence)

Claude writes a **self-contained page** (HTML / React / Markdown / template canvas) → it opens beside chat (or at a `claude.ai` URL) → the page runs in a **sandboxed `*.claudeusercontent.com` iframe** → Anthropic injects a bridge (`window.claude`, `window.storage`, patched `fetch` for Anthropic Messages) so the page can call Claude and optionally persist text — **without** your API keys.

## Two eras: legacy vs post–2026-09-16

| | Legacy artifacts | Newer artifacts (templates + file-backed) |
| --- | --- | --- |
| Created | Chat generations **before 2026-09-16** | Docs / Slides / Design / Dashboards / Motion, Claude Code publishes, current chat artifacts |
| New ones | Cannot create new legacy artifacts | Default path today |
| Publish / share | Still works | Yes |
| Storage while drafting | Often **silent until publish** | Help Center: new artifacts can store **without** publishing |
| AI inside the page | `window.claude.complete` / proxied Messages | Same family; first use asks permission |
| Edit model | Ask Claude in chat; code panel | Ask Claude **or** edit on canvas (docs/slides/design) |

When reading older blog posts (“no persistent storage”, “string-only complete”), check the date — several limits have been lifted or softened.

## What you can build (artifact types)

| Type | What it is | Typical stack |
| --- | --- | --- |
| Document / Markdown | Long-form content, specs, notes | Markdown → styled page; highlight → “Edit with Claude” |
| Code snippet | Reusable code block | Syntax-highlighted panel |
| Single-page website / tool | Interactive UI | HTML + CSS + JS, often React via Babel/CDN |
| Diagram | Flowcharts, architecture | Mermaid / SVG |
| Docs template | Collaborative living doc | First-party editor |
| Slides template | Deck + present mode | First-party editor; export PPTX/PDF |
| Design template | Mockups, landing pages | Canvas + design system |
| Dashboards template (beta) | Live charts from connected data platforms | Queries + refresh metadata |
| Motion template (beta) | Animated explainers → **MP4** | Team / Enterprise |
| Claude Code artifact | Live page from a coding session | HTML/MD under CSP; can declare connectors / downloads |

Claude creates an artifact when content is significant (~15+ lines), self-contained, editable/reusable, and likely to be revisited.

## Sandbox and CSP (what is hard)

Each page is one document. Relative multi-route sites do not work. Claude Code docs state the practical CSP shape:

| Constraint | Effect |
| --- | --- |
| Script CDNs | Allowlisted: `cdnjs.cloudflare.com`, `unpkg.com`, `cdn.jsdelivr.net` (selected `/npm/` paths), `cdn.tailwindcss.com`, `code.jquery.com` |
| Fonts | Google Fonts optional; blocked fonts fall back |
| Images | External image hosts generally blocked — **inline / data URIs** |
| `fetch` / XHR / WebSocket | Toward page origin + Google Fonts; **Anthropic Messages** via patched proxy (see API section). Arbitrary third-party APIs are historically blocked or unreliable — product post still listed “No external API calls (yet)” for Claude-powered apps; Claude Code connector calls go through **claude.ai**, not the page’s own network |
| Backend | None — no your-server auth, no multi-route app |
| Size | Rendered page ≤ ~16 MiB |
| Source | `.html` / `.htm` / `.md`, UTF-8 (or LE UTF-16 with BOM) |

### Browser APIs

| API | Status in classic interactive artifacts |
| --- | --- |
| React state / in-memory JS | ✅ Primary state model |
| `localStorage` / `sessionStorage` / IndexedDB | ❌ Typically blocked — use `window.storage` or memory |
| `window.storage` | ✅ Text KV, plan-gated (see Storage) |
| File upload via `<input type=file>` + FileReader | ✅ For feeding Claude Messages (PDF/image base64) |
| `window.fs.readFile` | Mentioned in older analysis-tool / artifact tooling — treat as host-injected, not portable |
| Downloads via `blob:` / `data:` links | ❌ Viewer blocks page-started downloads; Claude Code needs declared **downloads** capability |
| `window.open` / cookies / parent DOM | ❌ Sandboxed |

## Follow-up and conversation context

There are **three** different “next turn” loops. Mixing them up is the main source of confusion.

### A. Chat → Artifact (authoring loop)

1. User asks Claude to create/change the artifact.
2. Claude rewrites the underlying file/code and the panel updates (new **version**).
3. Edit an **earlier chat message** → forked conversation with its **own** artifact lineage.
4. Template artifacts: edit on canvas; Docs support highlight → “Edit with Claude”.
5. Errors: “Try fixing with Claude” copies error details into a new user message — **runtime errors inside the iframe are not automatically visible to the model**.

**Implication:** the main chat model does **not** see click state inside the iframe unless you paste it back, export a prompt, or (Claude Code) use comments / Send to Claude.

### B. Inside the artifact → Claude (runtime AI loop)

The page calls Claude itself. Usage bills the **viewer’s** plan; publisher pays $0 for their usage. No API keys in the page.

**History is not automatic.** You must resend prior turns (or app state) on every call:

```js
// Pattern Anthropic teaches for string-complete era — still valid as a prompt pattern
const conversationHistory = [
  { role: "user", content: "Hello" },
  { role: "assistant", content: "Hi — what should we triage?" },
  { role: "user", content: "Delay on van V-104" },
];

const prompt = `
COMPLETE conversation history (consider ALL of it):
${JSON.stringify(conversationHistory)}

Respond as a single JSON object:
{"response":"...","sentiment":"..."}
DO NOT OUTPUT ANYTHING OTHER THAN VALID JSON.
`;

const text = await window.claude.complete(prompt);
```

With the **Messages-shaped** path (proxied `fetch` to `https://api.anthropic.com/v1/messages`, or object form of `complete` where available), pass a real `messages` array — that is the correct place for follow-up context:

```js
const response = await fetch("https://api.anthropic.com/v1/messages", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    model: "claude-sonnet-4-20250514", // model id Claude instructs; no API key header
    max_tokens: 1024,
    system: "You are a fleet-ops coach. Return JSON only.",
    messages: conversationHistory,
  }),
});
const data = await response.json();
```

Observed reverse-engineering: browser `fetch` is monkey-patched; Anthropic URL is rewritten to  
`https://claude.ai/api/organizations/<org>/proxy/v1/messages`.

**Also ship app state**, not only chat turns — e.g. serialize board columns / game state as JSON in the system prompt or a tool result every call.

### C. Claude Code comments / live page (session loop)

- Page updates **in place** at the same URL as Claude republishes.
- Org share: comments; editors can **Send to Claude** / `@claude` to activate a thread.
- Auto-reply watches exist (version-gated); plan mode / permission mode still apply.
- “Copy as prompt” / export controls are the intentional way to send **interaction results** back into the terminal chat.

## User interactions (what works in-page)

Artifacts are normal DOM apps inside the iframe. Anything you can do with HTML/CSS/JS under CSP is fair game.

| Interaction | Possible? | Notes |
| --- | --- | --- |
| Click / tap buttons | ✅ | Prefer segmented controls over dense menus (same UX taste as MCP Apps guidelines) |
| Text inputs, forms | ✅ | Persist via React state or `window.storage` |
| Sliders, toggles, range | ✅ | Great for live-tuning transitions |
| Tooltips / title / hover cards | ✅ | Pure CSS or JS; no host API |
| Drag and drop | ✅ | e.g. triage board columns |
| Tabs / accordion / steppers | ✅ | Use in-page anchors for deep links (`#overview`) |
| Modals / popovers | ✅ inside iframe | Watch clipping; keep simple |
| Nested page scroll | ✅ | Unlike MCP Apps **inline** cards, artifacts are usually a full panel/page |
| Chat composer inside artifact | ✅ as UI | Does **not** auto-feed the host chat — use Claude API inside, or export text for the user to paste |
| Horizontal pan / maps / canvas | ✅ | Canvas/WebGL via allowlisted CDN libs |
| File picker | ✅ | Feed into Messages content blocks |
| Native share / OS calendar | ❌ from page | Mobile Claude tools (`event_create_v0`) are **chat tools**, not artifact APIs |

### Tooltips — patterns that survive the sandbox

```css
[data-tip] { position: relative; }
[data-tip]::after {
  content: attr(data-tip);
  position: absolute; bottom: calc(100% + 6px); left: 50%;
  transform: translateX(-50%) translateY(4px);
  opacity: 0; pointer-events: none;
  transition: opacity 120ms ease, transform 120ms ease;
  /* ...visuals... */
}
[data-tip]:hover::after,
[data-tip]:focus-visible::after {
  opacity: 1; transform: translateX(-50%) translateY(0);
}
```

Prefer `focus-visible` so keyboard users get the same affordance.

## Transitions and motion

| Approach | Possible? | Notes |
| --- | --- | --- |
| CSS `transition` / `transform` / `opacity` | ✅ | Default for UI chrome |
| CSS `@keyframes` / WAAPI | ✅ | |
| Framer Motion / heavy animation libs | ⚠️ | Only if on allowlisted CDN; keep bundle small (16 MiB page cap) |
| Claude Motion template | ✅ (Team/Ent beta) | First-party timeline editor → **MP4 export** — different from DIY CSS in a React artifact |
| Video generative footage | ❌ | Motion is code-driven animation, not Runway-style video gen |
| Cross-fade between artifact versions | Host UI | Version picker is Claude chrome, not your CSS |

Interactive tuning pattern (Claude Code docs literally recommend this): bind duration / delay / easing to sliders and animate a live preview.

## Claude API inside artifacts

### Surfaces that exist

| Surface | Shape | Returns | Notes |
| --- | --- | --- | --- |
| `window.claude.complete(prompt: string)` | Original “Claudeception” | `string` | Stateless; stuff history into the prompt |
| `window.claude.complete({ messages, ... })` | Newer helper (community / Design skill reports) | Final text | May support `model`, `max_tokens`, `system`, client `tools` with in-page `run` |
| `fetch('https://api.anthropic.com/v1/messages', …)` | Full Messages API body | JSON | No `x-api-key`; proxy bills viewer |

### Dynamic behavior on events

Typical event → Claude patterns:

| Event | Pattern |
| --- | --- |
| Button click | `onClick` → build messages → `complete` / `fetch` → setState |
| Debounced typing | Coach / search-as-you-type (watch rate limits) |
| File selected | FileReader → base64 document/image block → Messages |
| Timer / interval | Poll-style refresh of summary (prefer user Refresh control) |
| Drag end | Serialize board → ask Claude to critique ordering |
| Storage change | Re-render from `window.storage.get` |
| Connector refresh (Claude Code) | Declared MCP connectors; viewer’s account; permission prompt |

### Rate limits and tools (community-observed)

Reports around the Design / prototype helper:

- Default model often Haiku-class for cheap loops; Sonnet when instructed.
- ~15 calls / minute / user including tool-loop iterations.
- Client tools: `run: async (input) => string`, max ~8 model calls per loop; server tools (web search etc.) rejected.
- No streaming in the simple helper path.

Always **prototype completions in the analysis tool** first — the main chat cannot see whether in-artifact orchestration succeeded.

### Multimodal

July 2025+ path: PDF / image / code file uploads inside the app → base64 `document` / `image` content blocks in Messages. Viewers authenticate; usage on their quota.

## Storage (`window.storage`)

Plan gate: **Pro / Max / Team / Enterprise** (not Free). Text only. **20 MB / artifact**. Personal vs shared pools are isolated.

```js
// Community-observed shape (alistigo snapshot) — verify in your session
await window.storage.set("draft", JSON.stringify(state), false); // personal
const row = await window.storage.get("draft", false);
await window.storage.delete("draft", false);
const keys = await window.storage.list("prefix/", false);
// third arg true → shared pool
```

| Pitfall | Detail |
| --- | --- |
| Silent no-op while drafting | Legacy: storage often only works **after publish** |
| Unpublish deletes data | Permanent for that artifact’s pools |
| Shared has no author | No identity / ACL inside shared KV |
| No binary | Images/files must live elsewhere or as data URIs in the page (size!) |

## Connectors / “connect your apps”

Artifacts can use apps connected to Claude (Asana, Calendar, Slack, custom connectors). First use: permission UI; per-tool opt-out remembered. **Each viewer uses their own connections.** Tools that require per-action approval are unavailable to artifacts. Org owners can disable.

Claude Code published pages: declare connectors at publish time; page cannot call undeclared ones; local `.mcp.json` servers can feed **build time** but not the published page.

## Sharing, forking, versions

- Default private; Share → org and/or public (policy-dependent).
- Public AI-powered artifacts still need viewer sign-in for Claude calls.
- Legacy: Copy code → new chat to fork.
- Versions: each republish; Share UI can pin which version viewers see.
- Deep links: `#section` anchors for tabs/views.

## What is **not** possible (honest list)

1. Multi-page routed web app with a real backend you control.
2. Reliable arbitrary third-party `fetch` (weather, your private API) without a Claude-mediated connector / proxy path.
3. Automatic round-trip of iframe UI state into the **authoring** chat.
4. Server-side secrets in the page (everything is visible to viewers who open DevTools / Copy).
5. Binary blob storage in `window.storage`.
6. Viewer identity + ACLs inside shared storage.
7. Streaming tokens in the simple complete helper (as of community reports).
8. Nesting MCP Apps protocol (`ui/message`, `callServerTool`) — that is a **different** iframe product.
9. Creating new **legacy** artifact types after the 2026-09-16 cutoff.
10. Guaranteed `localStorage` persistence.

## Mock data used in this exploration

Fleet-ops themed mocks (same product neighborhood as the MCP Apps gallery, different runtime):

| Entity | Example |
| --- | --- |
| Vans | `V-104`, `V-221`, `V-318` |
| Regions | SOMA, Mission, Sunset |
| Statuses | `on_time`, `delayed`, `yard` |
| Delay reason | “Double-parked on Folsom” |
| KPI | on-time % `87.4`, open incidents `3` |

Mocks live in [`src/mock-data.ts`](./src/mock-data.ts) and are embedded in the gallery artifact.

## Open questions (ask before we deepen)

See the PR summary / chat follow-ups — anything unclear is listed there rather than guessed here.
