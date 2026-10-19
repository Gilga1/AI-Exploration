import assert from "node:assert/strict";
import { after, before, describe, it } from "node:test";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import {
  GLOSSARY_MD,
  GLOSSARY_URI,
  MY_REGIONS_URI,
  todaySnapshotMd,
} from "../src/catalog.ts";
import { createServer } from "../server.ts";

describe("MCP prompts and resources", () => {
  let client: Client;
  let close = async () => {};

  before(async () => {
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    const server = createServer();
    client = new Client({ name: "catalog-test", version: "0.0.1" });
    await Promise.all([server.connect(serverTransport), client.connect(clientTransport)]);
    close = async () => {
      await client.close();
      await server.close();
    };
  });

  after(async () => {
    await close();
  });

  it("advertises prompts and resources capabilities", () => {
    const caps = client.getServerCapabilities();
    assert.ok(caps?.prompts);
    assert.ok(caps?.resources);
  });

  it("lists named starter prompts", async () => {
    const { prompts } = await client.listPrompts();
    const names = prompts.map((p) => p.name).sort();
    assert.deepEqual(names, [
      "delayed_vans_today",
      "fleet_briefing_story",
      "incident_playbook",
      "open_fleet_ops",
      "open_ops_board",
      "region_ops_report",
    ]);
    const region = prompts.find((p) => p.name === "region_ops_report");
    assert.equal(region?.arguments?.some((a) => a.name === "region" && a.required), true);
  });

  it("returns a multi-step workflow from prompts/get", async () => {
    const result = await client.getPrompt({
      name: "region_ops_report",
      arguments: { region: "Mission" },
    });
    const text = result.messages[0]?.content;
    assert.equal(result.messages[0]?.role, "user");
    assert.ok(text && text.type === "text");
    if (text.type === "text") {
      assert.match(text.text, /Mission/);
      assert.match(text.text, /get_region_summary/);
      assert.match(text.text, /show_operations_dashboard/);
      assert.match(text.text, /Do not skip/);
    }
  });

  it("lists glossary, entitlements, snapshot, and region briefings", async () => {
    const { resources } = await client.listResources();
    const uris = resources.map((r) => r.uri);
    assert.ok(uris.includes(GLOSSARY_URI));
    assert.ok(uris.includes(MY_REGIONS_URI));
    assert.ok(uris.includes("ops://snapshot/today"));
    assert.ok(uris.includes("ops://claude-product-notes"));
    assert.ok(uris.includes("ops://region/Mission"));
    assert.ok(uris.some((uri) => uri.startsWith("ui://")));
  });

  it("reads glossary and snapshot text", async () => {
    const glossary = await client.readResource({ uri: GLOSSARY_URI });
    const glossaryText = glossary.contents[0] && "text" in glossary.contents[0] ? glossary.contents[0].text : "";
    assert.equal(glossaryText, GLOSSARY_MD);

    const snapshot = await client.readResource({ uri: "ops://snapshot/today" });
    const snapshotText = snapshot.contents[0] && "text" in snapshot.contents[0] ? snapshot.contents[0].text : "";
    assert.equal(snapshotText, todaySnapshotMd());
    assert.match(snapshotText, /VAN-07/);
  });

  it("resolves the region URI template", async () => {
    const templates = await client.listResourceTemplates();
    assert.ok(templates.resourceTemplates.some((t) => t.uriTemplate === "ops://region/{region}"));

    const briefing = await client.readResource({ uri: "ops://region/SOMA" });
    const text = briefing.contents[0] && "text" in briefing.contents[0] ? briefing.contents[0].text : "";
    assert.match(text, /SOMA/);
    assert.match(text, /VAN-14/);
  });
});
