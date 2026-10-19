import assert from "node:assert/strict";
import { after, before, describe, it } from "node:test";
import { startHttpServer } from "../server.ts";

const initializeBody = {
  jsonrpc: "2.0",
  id: 1,
  method: "initialize",
  params: {
    protocolVersion: "2025-03-26",
    capabilities: {},
    clientInfo: { name: "http-test", version: "0.0.1" },
  },
};

describe("HTTP MCP transport", () => {
  let base = "";
  let close: () => Promise<void> = async () => {};

  before(async () => {
    const server = await startHttpServer(0, "127.0.0.1");
    base = `http://127.0.0.1:${server.port}`;
    close = server.close;
  });

  after(async () => {
    await close();
  });

  it("exposes a health endpoint", async () => {
    const res = await fetch(`${base}/health`);
    assert.equal(res.status, 200);
    const body = (await res.json()) as {
      ok: boolean;
      transport: string;
      prompts?: string[];
      resources?: string[];
    };
    assert.equal(body.ok, true);
    assert.equal(body.transport, "http");
    assert.ok(Array.isArray(body.prompts) && body.prompts.includes("delayed_vans_today"));
    assert.ok(Array.isArray(body.resources) && body.resources.includes("ops://glossary"));
  });

  it("answers MCP initialize over Streamable HTTP", async () => {
    const res = await fetch(`${base}/mcp`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json, text/event-stream",
      },
      body: JSON.stringify(initializeBody),
    });
    assert.equal(res.status, 200);
    const payload = (await res.json()) as {
      result?: { serverInfo?: { name?: string } };
    };
    assert.equal(payload.result?.serverInfo?.name, "fleet-ops");
  });
});
