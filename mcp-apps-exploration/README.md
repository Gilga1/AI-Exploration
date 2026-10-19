# Fleet Ops (MCP Apps connector)

Territory Trade Report–style **custom connector** for Claude: mocked SF fleet ops with an interactive MCP App.

This is **not** Claude Dashboards or Claude Motion. Those are Anthropic product features — see [`CLAUDE_PRODUCT.md`](./CLAUDE_PRODUCT.md).

## What you can test

| Layer | Behavior |
| --- | --- |
| **Domain tools** | `list_delayed_vans`, `filter_fleet`, `refresh_fleet_snapshot`, `get_vehicle_detail`, `get_region_summary` — data without (or with) UI |
| **UI tools** | `open_fleet_ops`, `show_live_map`, `show_operations_dashboard`, … — open the iframe |
| **In-app actions** | Filter / refresh / drill use **`callServerTool`** → **no Claude turn**, no Enter |
| **Explain / Ask Claude** | Uses `sendMessage` → on **Claude Desktop only fills the composer**; you still press **Send** ([claude-ai-mcp#33](https://github.com/anthropics/claude-ai-mcp/issues/33)) |
| **+ menu prompts / resources** | Same recipes as Territory Trade: trade-today, weekly region report, glossary, entitlements |

## Run

```bash
cd mcp-apps-exploration
npm install
npm test
npm run build
npm run serve          # http://127.0.0.1:3001/mcp
```

Health: `GET http://127.0.0.1:3001/health`

**Claude Desktop:** bridge HTTP with `mcp-remote` (see below) or a custom connector URL.

```json
{
  "mcpServers": {
    "fleet-ops": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://127.0.0.1:3001/mcp", "--transport", "http-only"]
    }
  }
}
```

Then ask: “Open Fleet Ops” or “Show delayed vans today.”

## Prompts (+ → Connectors)

| Prompt | Job |
| --- | --- |
| `open_fleet_ops` | Open connector home |
| `delayed_vans_today` | Trade-today analog: `list_delayed_vans` + map |
| `region_ops_report` | Weekly report analog (region arg) |
| `incident_playbook` | Sheets playbook |
| `open_ops_board` | KPI board walkthrough |
| `fleet_briefing_story` | CSS briefing POC (not Motion) |

## Resources

| URI | Role |
| --- | --- |
| `ops://glossary` | Van / delayed / on-time labels |
| `ops://my-regions` | Mock entitlements (SOMA + Mission) |
| `ops://dashboard-schema` | How to read the ops board |
| `ops://claude-product-notes` | Dashboards/Motion ≠ this connector |
| `ops://snapshot/today` | Frozen snapshot |
| `ops://region/{region}` | Region briefing |

## Layout lab (no Claude)

```bash
npm run preview
```

Open `http://localhost:4177/preview/index.html`.

## Honest limits

- Mock data only — no BigQuery / Salesforce.
- Desktop `sendMessage` = composer prefill, not auto-send.
- Briefing tab ≠ Claude Motion MP4.
- See `RESEARCH.md` for MCP Apps host capabilities.
