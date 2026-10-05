import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");

describe("MCP Apps wiring", () => {
  it("registers a ui:// resource and display-mode requests", () => {
    const server = readFileSync(path.join(root, "server.ts"), "utf8");
    assert.match(server, /ui:\/\/mcp-apps-exploration\/gallery.html/);
    assert.match(server, /registerAppTool/);
    assert.match(server, /RESOURCE_MIME_TYPE/);
    assert.match(server, /show_live_map/);
    assert.match(server, /show_operations_dashboard/);
    assert.match(server, /StreamableHTTPServerTransport/);
    assert.doesNotMatch(server, /StdioServerTransport/);
  });

  it("does not hardcode Claude chat-column width in the app CSS", () => {
    const css = readFileSync(path.join(root, "src/ui/styles.css"), "utf8");
    assert.match(css, /width: 100%/);
    assert.doesNotMatch(css, /width:\s*736px/);
  });

  it("asks the host for fullscreen instead of assuming inline-only", () => {
    const app = readFileSync(path.join(root, "src/ui/app.ts"), "utf8");
    assert.match(app, /requestDisplayMode/);
    assert.match(app, /availableDisplayModes:\s*\["inline", "fullscreen", "pip"\]/);
  });
});
