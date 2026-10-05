import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { FLEET_SNAPSHOT, tickVehicles, parseSnapshot } from "../src/mock-data.ts";
import { describeDimensions, SPEC_NOTES } from "../src/host-context.ts";

describe("mocked fleet data", () => {
  it("has enough vehicles and kpis for the gallery", () => {
    assert.ok(FLEET_SNAPSHOT.vehicles.length >= 5);
    assert.equal(FLEET_SNAPSHOT.kpis.length, 4);
    assert.ok(FLEET_SNAPSHOT.alerts.some((a) => a.severity === "critical"));
  });

  it("animates only moving vehicles", () => {
    const next = tickVehicles(FLEET_SNAPSHOT, 60);
    const idle = FLEET_SNAPSHOT.vehicles.find((v) => v.status === "idle")!;
    const idleNext = next.vehicles.find((v) => v.id === idle.id)!;
    assert.equal(idleNext.lat, idle.lat);
    const moving = FLEET_SNAPSHOT.vehicles.find((v) => v.status === "en_route")!;
    const movingNext = next.vehicles.find((v) => v.id === moving.id)!;
    assert.notEqual(`${movingNext.lat},${movingNext.lng}`, `${moving.lat},${moving.lng}`);
  });

  it("falls back when payload is malformed", () => {
    assert.equal(parseSnapshot(null).city, "San Francisco");
  });
});

describe("host context facts", () => {
  it("treats width as host-controlled, not a protocol constant", () => {
    assert.equal(SPEC_NOTES.protocolVersion, "2026-01-26");
    assert.deepEqual([...SPEC_NOTES.displayModes], ["inline", "fullscreen", "pip"]);
    assert.equal(SPEC_NOTES.claudeDesktopObservedInline.width, 736);
    assert.notEqual(SPEC_NOTES.specInitializeExampleWidth, SPEC_NOTES.claudeDesktopObservedInline.width);
    assert.match(
      describeDimensions({ width: 1200, maxHeight: 5000 }),
      /fixed width 1200px/,
    );
    assert.match(
      describeDimensions({ maxWidth: 400, height: 240 }),
      /flexible up to 400px/,
    );
  });
});
