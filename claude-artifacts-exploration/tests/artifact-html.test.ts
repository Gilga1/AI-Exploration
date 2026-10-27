import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

describe("fleet-ops-lab artifact", () => {
  const html = readFileSync(join(root, "artifacts/fleet-ops-lab.html"), "utf8");

  it("documents the Claude APIs it exercises", () => {
    assert.match(html, /window\.claude\.complete/);
    assert.match(html, /api\.anthropic\.com\/v1\/messages/);
    assert.match(html, /window\.storage/);
  });

  it("covers the exploration tabs", () => {
    for (const tab of [
      "overview",
      "interactions",
      "transitions",
      "followup",
      "events",
      "storage",
    ]) {
      assert.match(html, new RegExp(`id: "${tab}"`));
    }
  });

  it("embeds mock van ids", () => {
    assert.match(html, /V-104/);
    assert.match(html, /V-512/);
  });
});
