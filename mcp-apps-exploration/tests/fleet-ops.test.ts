import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { filterFleet, listDelayedVans, refreshFleetSnapshot } from "../src/fleet-ops.ts";
import { FLEET_SNAPSHOT } from "../src/mock-data.ts";

describe("fleet ops domain", () => {
  it("lists delayed and critical-hold vans", () => {
    const vans = listDelayedVans(FLEET_SNAPSHOT);
    assert.ok(vans.some((v) => v.id === "VAN-07"));
    assert.ok(vans.some((v) => v.id === "VAN-14"));
  });

  it("filters by status without a Claude turn", () => {
    const filtered = filterFleet(FLEET_SNAPSHOT, { status: "delayed" });
    assert.equal(filtered.vehicles.every((v) => v.status === "delayed"), true);
  });

  it("refreshes generatedAt", () => {
    const next = refreshFleetSnapshot(FLEET_SNAPSHOT);
    assert.notEqual(next.generatedAt, FLEET_SNAPSHOT.generatedAt);
  });
});
