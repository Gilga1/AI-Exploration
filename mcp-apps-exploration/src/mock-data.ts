export type VehicleStatus = "en_route" | "idle" | "delayed" | "charging";

export interface Vehicle {
  id: string;
  driver: string;
  status: VehicleStatus;
  lat: number;
  lng: number;
  heading: number;
  speedKph: number;
  etaMin: number;
  load: string;
}

export interface Site {
  id: string;
  name: string;
  kind: "hub" | "customer" | "charger";
  lat: number;
  lng: number;
}

export interface Kpi {
  id: string;
  label: string;
  value: number;
  unit: string;
  deltaPct: number;
  spark: number[];
}

export interface RegionRow {
  region: string;
  onTimePct: number;
  volume: number;
  incidents: number;
}

export interface Alert {
  id: string;
  severity: "info" | "warning" | "critical";
  title: string;
  body: string;
  vehicleId?: string;
}

export interface FleetSnapshot {
  generatedAt: string;
  city: string;
  bbox: { west: number; south: number; east: number; north: number };
  vehicles: Vehicle[];
  sites: Site[];
  kpis: Kpi[];
  regions: RegionRow[];
  alerts: Alert[];
  hourlyVolume: number[];
}

const SF_BBOX = {
  west: -122.52,
  south: 37.72,
  east: -122.35,
  north: 37.82,
};

export const FLEET_SNAPSHOT: FleetSnapshot = {
  generatedAt: "2026-10-05T16:00:00.000Z",
  city: "San Francisco",
  bbox: SF_BBOX,
  vehicles: [
    {
      id: "VAN-14",
      driver: "Priya N.",
      status: "en_route",
      lat: 37.789,
      lng: -122.401,
      heading: 42,
      speedKph: 28,
      etaMin: 12,
      load: "Same-day parcels",
    },
    {
      id: "VAN-07",
      driver: "Marcus L.",
      status: "delayed",
      lat: 37.764,
      lng: -122.433,
      heading: 190,
      speedKph: 9,
      etaMin: 34,
      load: "Cold chain",
    },
    {
      id: "VAN-22",
      driver: "Elena K.",
      status: "idle",
      lat: 37.776,
      lng: -122.394,
      heading: 0,
      speedKph: 0,
      etaMin: 0,
      load: "Empty",
    },
    {
      id: "VAN-31",
      driver: "Theo R.",
      status: "charging",
      lat: 37.804,
      lng: -122.432,
      heading: 270,
      speedKph: 0,
      etaMin: 18,
      load: "Grocery",
    },
    {
      id: "VAN-03",
      driver: "Amelia S.",
      status: "en_route",
      lat: 37.748,
      lng: -122.419,
      heading: 12,
      speedKph: 34,
      etaMin: 8,
      load: "Pharmacy",
    },
    {
      id: "VAN-19",
      driver: "Jonah P.",
      status: "en_route",
      lat: 37.801,
      lng: -122.409,
      heading: 310,
      speedKph: 22,
      etaMin: 21,
      load: "Retail restock",
    },
  ],
  sites: [
    { id: "HUB-SOMA", name: "SoMa Hub", kind: "hub", lat: 37.778, lng: -122.396 },
    { id: "HUB-MARN", name: "Marina Hub", kind: "hub", lat: 37.803, lng: -122.436 },
    { id: "CUST-1", name: "Ferry Building", kind: "customer", lat: 37.795, lng: -122.393 },
    { id: "CUST-2", name: "Mission Plaza", kind: "customer", lat: 37.759, lng: -122.421 },
    { id: "CHG-1", name: "Embarcadero charger", kind: "charger", lat: 37.806, lng: -122.405 },
  ],
  kpis: [
    { id: "ontime", label: "On-time", value: 94.2, unit: "%", deltaPct: 1.4, spark: [88, 90, 91, 89, 93, 94, 94.2] },
    { id: "active", label: "Active vans", value: 4, unit: "", deltaPct: 0, spark: [3, 4, 5, 4, 4, 5, 4] },
    { id: "eta", label: "Median ETA", value: 14, unit: "min", deltaPct: -8.2, spark: [22, 19, 18, 16, 15, 14, 14] },
    { id: "incidents", label: "Open incidents", value: 2, unit: "", deltaPct: -33, spark: [5, 4, 4, 3, 3, 2, 2] },
  ],
  regions: [
    { region: "SOMA", onTimePct: 97, volume: 142, incidents: 0 },
    { region: "Mission", onTimePct: 88, volume: 98, incidents: 1 },
    { region: "Marina", onTimePct: 95, volume: 61, incidents: 0 },
    { region: "Sunset", onTimePct: 91, volume: 74, incidents: 1 },
    { region: "Richmond", onTimePct: 96, volume: 53, incidents: 0 },
  ],
  alerts: [
    {
      id: "ALT-1",
      severity: "warning",
      title: "VAN-07 delayed on 16th St",
      body: "Traffic incident near Mission Plaza. Cold-chain window closes in 28 minutes.",
      vehicleId: "VAN-07",
    },
    {
      id: "ALT-2",
      severity: "info",
      title: "VAN-31 charging",
      body: "Battery at 34%. Estimated ready in 18 minutes at Marina Hub.",
      vehicleId: "VAN-31",
    },
    {
      id: "ALT-3",
      severity: "critical",
      title: "Customer hold: Ferry Building",
      body: "Dock access closed until 16:40. Reroute VAN-14 or hold at SoMa Hub?",
      vehicleId: "VAN-14",
    },
  ],
  hourlyVolume: [12, 18, 24, 41, 63, 88, 97, 84, 71, 66, 58, 44],
};

export function tickVehicles(snapshot: FleetSnapshot, dtSec: number): FleetSnapshot {
  const { west, south, east, north } = snapshot.bbox;
  const vehicles = snapshot.vehicles.map((v) => {
    if (v.status !== "en_route" && v.status !== "delayed") return v;
    const speed = v.status === "delayed" ? v.speedKph * 0.35 : v.speedKph;
    const km = (speed * dtSec) / 3600;
    const dLat = (km / 111) * Math.cos((v.heading * Math.PI) / 180);
    const dLng = (km / 85) * Math.sin((v.heading * Math.PI) / 180);
    let lat = v.lat + dLat;
    let lng = v.lng + dLng;
    let heading = v.heading;
    if (lat > north || lat < south) {
      heading = 180 - heading;
      lat = Math.min(north, Math.max(south, lat));
    }
    if (lng > east || lng < west) {
      heading = -heading;
      lng = Math.min(east, Math.max(west, lng));
    }
    return { ...v, lat, lng, heading: (heading + 360) % 360 };
  });
  return { ...snapshot, vehicles, generatedAt: new Date().toISOString() };
}

export function parseSnapshot(raw: unknown): FleetSnapshot {
  if (!raw || typeof raw !== "object") return FLEET_SNAPSHOT;
  const candidate = raw as Partial<FleetSnapshot>;
  if (!Array.isArray(candidate.vehicles) || !Array.isArray(candidate.kpis)) {
    return FLEET_SNAPSHOT;
  }
  return { ...FLEET_SNAPSHOT, ...candidate } as FleetSnapshot;
}
