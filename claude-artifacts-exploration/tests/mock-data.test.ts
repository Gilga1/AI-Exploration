import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  VANS,
  FLEET_SUMMARY,
  delayedVans,
  vanById,
  filterByRegion,
} from "../src/mock-data.ts";

describe("mock fleet data", () => {
  it("has delayed vans matching summary count", () => {
    assert.equal(delayedVans().length, FLEET_SUMMARY.delayedCount);
  });

  it("looks up vans by id", () => {
    assert.equal(vanById("V-104")?.region, "SOMA");
    assert.equal(vanById("nope"), undefined);
  });

  it("filters by region", () => {
    const soma = filterByRegion("SOMA");
    assert.ok(soma.length >= 1);
    assert.ok(soma.every((v) => v.region === "SOMA"));
  });

  it("keeps a stable fleet size for demos", () => {
    assert.equal(VANS.length, 5);
  });
});
