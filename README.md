# MCP Apps exploration (Fleet Ops)

This branch contains **only** the MCP Apps connector under [`mcp-apps-exploration/`](./mcp-apps-exploration/).

Territory Trade–style mocked SF fleet ops for Claude: MCP App UI, domain tools, prompts, and resources. Claude Dashboards / Motion are **not** included here — see [`mcp-apps-exploration/CLAUDE_PRODUCT.md`](./mcp-apps-exploration/CLAUDE_PRODUCT.md).

## Quick start

```bash
cd mcp-apps-exploration
npm install
npm test
npm run build
npm run serve    # http://127.0.0.1:3001/mcp
```

Documentation:

- [`mcp-apps-exploration/README.md`](./mcp-apps-exploration/README.md) — run in Claude Desktop, tools, prompts
- [`mcp-apps-exploration/RESEARCH.md`](./mcp-apps-exploration/RESEARCH.md) — MCP Apps capabilities and limits

## Branch

| Branch | Purpose |
|--------|---------|
| `feature/mcp-apps-exploration` | Fleet Ops MCP connector (this tree) |

The monorepo index for all AI Exploration projects lives on `main`.

## License

See [LICENSE](LICENSE).
