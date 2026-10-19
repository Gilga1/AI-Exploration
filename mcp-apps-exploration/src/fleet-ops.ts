/**
 * Domain helpers for the Fleet Ops connector (Territory Trade Report analog).
 * Pure functions over mocked snapshot — used by tools and tests.
 */
import { FLEET_SNAPSHOT, type FleetSnapshot, type Vehicle, type VehicleStatus } from "./mock-data.ts";

export type FleetFilter = {
  status?: VehicleStatus | "all";
  region?: string | "all";
  /** Raise SLA target → flag regions below this on-time %. */
  slaTarget?: number;
};

export type FilteredFleet = FleetSnapshot & {
  filter: FleetFilter;
  view?: string;
  focusVehicleId?: string;
};

const REGION_VANS: Record<string, string[]> = {
  Mission: ["VAN-07", "VAN-03"],
  SOMA: ["VAN-14", "VAN-22"],
  Marina: ["VAN-31"],
  Sunset: ["VAN-19"],
  Richmond: [],
};

export function vansForRegion(region: string): string[] {
  return REGION_VANS[region] ?? [];
}

export function regionForVan(vanId: string): string | undefined {
  for (const [region, vans] of Object.entries(REGION_VANS)) {
    if (vans.includes(vanId)) return region;
  }
  return undefined;
}

export function listDelayedVans(snapshot: FleetSnapshot = FLEET_SNAPSHOT): Vehicle[] {
  const criticalIds = new Set(
    snapshot.alerts.filter((a) => a.severity === "critical" && a.vehicleId).map((a) => a.vehicleId!),
  );
  return snapshot.vehicles.filter((v) => v.status === "delayed" || criticalIds.has(v.id));
}

export function filterFleet(snapshot: FleetSnapshot, filter: FleetFilter): FilteredFleet {
  const status = filter.status ?? "all";
  const region = filter.region ?? "all";
  let vehicles = snapshot.vehicles;
  if (status !== "all") {
    vehicles = vehicles.filter((v) => v.status === status);
  }
  if (region !== "all") {
    const allowed = new Set(vansForRegion(region));
    vehicles = vehicles.filter((v) => allowed.has(v.id));
  }
  const vehicleIds = new Set(vehicles.map((v) => v.id));
  const alerts = snapshot.alerts.filter((a) => !a.vehicleId || vehicleIds.has(a.vehicleId));
  const regions =
    region === "all"
      ? snapshot.regions
      : snapshot.regions.filter((r) => r.region.toLowerCase() === region.toLowerCase());

  const sla = filter.slaTarget;
  const flagged =
    sla != null ? regions.filter((r) => r.onTimePct < sla).map((r) => r.region) : [];

  return {
    ...snapshot,
    vehicles,
    alerts,
    regions,
    filter: { ...filter, status, region },
    generatedAt: new Date().toISOString(),
    // carry SLA flags for UI caption
    ...(flagged.length ? { slaBreaches: flagged } : {}),
  } as FilteredFleet & { slaBreaches?: string[] };
}

export function refreshFleetSnapshot(base: FleetSnapshot = FLEET_SNAPSHOT): FleetSnapshot {
  // Mock “live refresh”: bump generatedAt and nudge ETA / sparklines slightly.
  const jitter = (n: number, amt = 0.3) => Math.round((n + (Math.random() - 0.5) * amt) * 10) / 10;
  return {
    ...base,
    generatedAt: new Date().toISOString(),
    kpis: base.kpis.map((k) => ({
      ...k,
      value: k.id === "ontime" ? jitter(k.value, 0.4) : k.value,
      spark: [...k.spark.slice(1), k.value],
    })),
    vehicles: base.vehicles.map((v) =>
      v.status === "en_route" || v.status === "delayed"
        ? { ...v, etaMin: Math.max(1, v.etaMin + Math.round((Math.random() - 0.5) * 4)) }
        : v,
    ),
  };
}

export function vehicleDetail(vehicleId: string, snapshot: FleetSnapshot = FLEET_SNAPSHOT) {
  const vehicle = snapshot.vehicles.find((v) => v.id === vehicleId);
  if (!vehicle) {
    return { found: false as const, vehicleId, message: `Unknown van ${vehicleId}` };
  }
  const alerts = snapshot.alerts.filter((a) => a.vehicleId === vehicleId);
  const region = regionForVan(vehicleId);
  return {
    found: true as const,
    vehicle,
    region,
    alerts,
    siteHint: snapshot.sites.find((s) =>
      region === "Marina" ? s.id === "HUB-MARN" : s.kind === "hub",
    ),
  };
}

export function delayedVansTableMarkdown(snapshot: FleetSnapshot = FLEET_SNAPSHOT): string {
  const rows = listDelayedVans(snapshot);
  if (!rows.length) return "No delayed or critical-hold vans in the mock snapshot.";
  const lines = [
    "| Van | Driver | Status | Load | ETA | Region |",
    "| --- | --- | --- | --- | --- | --- |",
    ...rows.map((v) => {
      const region = regionForVan(v.id) ?? "—";
      return `| ${v.id} | ${v.driver} | ${v.status} | ${v.load} | ${v.etaMin} min | ${region} |`;
    }),
  ];
  return lines.join("\n");
}
