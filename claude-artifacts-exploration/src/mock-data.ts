/** Mock fleet-ops data — same neighborhood as MCP Apps gallery, Artifact runtime. */

export type VanStatus = "on_time" | "delayed" | "yard";

export interface Van {
  id: string;
  region: "SOMA" | "Mission" | "Sunset";
  status: VanStatus;
  delayMinutes: number;
  reason: string | null;
  driver: string;
  lastPing: string;
}

export interface RegionKpi {
  region: string;
  onTimePct: number;
  openIncidents: number;
  activeVans: number;
}

export const VANS: Van[] = [
  {
    id: "V-104",
    region: "SOMA",
    status: "delayed",
    delayMinutes: 18,
    reason: "Double-parked on Folsom",
    driver: "A. Chen",
    lastPing: "2026-10-27T04:12:00Z",
  },
  {
    id: "V-221",
    region: "Mission",
    status: "on_time",
    delayMinutes: 0,
    reason: null,
    driver: "M. Ortiz",
    lastPing: "2026-10-27T04:14:00Z",
  },
  {
    id: "V-318",
    region: "Sunset",
    status: "yard",
    delayMinutes: 0,
    reason: null,
    driver: "R. Singh",
    lastPing: "2026-10-27T03:55:00Z",
  },
  {
    id: "V-407",
    region: "SOMA",
    status: "on_time",
    delayMinutes: 2,
    reason: null,
    driver: "J. Park",
    lastPing: "2026-10-27T04:15:00Z",
  },
  {
    id: "V-512",
    region: "Mission",
    status: "delayed",
    delayMinutes: 27,
    reason: "Loading dock queue at 16th",
    driver: "L. Nguyen",
    lastPing: "2026-10-27T04:10:00Z",
  },
];

export const REGION_KPIS: RegionKpi[] = [
  { region: "SOMA", onTimePct: 84.2, openIncidents: 2, activeVans: 14 },
  { region: "Mission", onTimePct: 91.0, openIncidents: 1, activeVans: 11 },
  { region: "Sunset", onTimePct: 88.5, openIncidents: 0, activeVans: 9 },
];

export const FLEET_SUMMARY = {
  onTimePct: 87.4,
  openIncidents: 3,
  delayedCount: VANS.filter((v) => v.status === "delayed").length,
  asOf: "2026-10-27T04:15:00Z",
};

export function delayedVans(): Van[] {
  return VANS.filter((v) => v.status === "delayed");
}

export function vanById(id: string): Van | undefined {
  return VANS.find((v) => v.id === id);
}

export function filterByRegion(region: string): Van[] {
  return VANS.filter((v) => v.region === region);
}
