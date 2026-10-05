import type { FleetSnapshot, Vehicle } from "../mock-data.ts";

const STATUS_COLOR: Record<Vehicle["status"], string> = {
  en_route: "#4682D5",
  idle: "#599130",
  delayed: "#A87829",
  charging: "#80AADD",
};

export function mountMap(root: HTMLElement, snapshot: FleetSnapshot, onSelect: (v: Vehicle) => void) {
  root.innerHTML = `
    <div class="map-shell">
      <canvas id="fleet-map" aria-label="Live fleet map"></canvas>
      <div class="map-legend">
        <span><i class="dot en_route"></i> En route</span>
        <span><i class="dot delayed"></i> Delayed</span>
        <span><i class="dot idle"></i> Idle</span>
        <span><i class="dot charging"></i> Charging</span>
      </div>
      <div class="map-hint">Drag to pan · scroll to zoom · tap a van for details</div>
    </div>
  `;
  const canvas = root.querySelector("canvas") as HTMLCanvasElement;
  const ctx = canvas.getContext("2d");
  if (!ctx) return () => {};

  let dpr = 1;
  let w = 0;
  let h = 0;
  let scale = 1;
  let panX = 0;
  let panY = 0;
  let dragging = false;
  let lastX = 0;
  let lastY = 0;
  let local = snapshot;
  let raf = 0;
  let lastTs = performance.now();

  const project = (lng: number, lat: number) => {
    const { west, south, east, north } = local.bbox;
    const x = ((lng - west) / (east - west)) * w;
    const y = ((north - lat) / (north - south)) * h;
    return { x: x * scale + panX, y: y * scale + panY };
  };

  const resize = () => {
    const rect = canvas.getBoundingClientRect();
    dpr = window.devicePixelRatio || 1;
    w = Math.max(1, rect.width);
    h = Math.max(1, rect.height);
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };

  const drawGrid = () => {
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--color-background-secondary") || "#262624";
    ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = "rgba(222,220,209,0.12)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 8; i++) {
      ctx.beginPath();
      ctx.moveTo((i / 8) * w * scale + panX, panY);
      ctx.lineTo((i / 8) * w * scale + panX, h * scale + panY);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(panX, (i / 8) * h * scale + panY);
      ctx.lineTo(w * scale + panX, (i / 8) * h * scale + panY);
      ctx.stroke();
    }
    ctx.fillStyle = "rgba(70,130,213,0.08)";
    const bay = [
      project(-122.52, 37.81),
      project(-122.47, 37.82),
      project(-122.39, 37.81),
      project(-122.37, 37.79),
      project(-122.38, 37.73),
      project(-122.52, 37.73),
    ];
    ctx.beginPath();
    bay.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
    ctx.closePath();
    ctx.fill();
  };

  const draw = (ts: number) => {
    const dt = Math.min(0.05, (ts - lastTs) / 1000);
    lastTs = ts;
    const { west, south, east, north } = local.bbox;
    local = {
      ...local,
      vehicles: local.vehicles.map((v) => {
        if (v.status !== "en_route" && v.status !== "delayed") return v;
        const speed = v.status === "delayed" ? 6 : 18;
        const km = (speed * dt) / 3600;
        let lat = v.lat + (km / 111) * Math.cos((v.heading * Math.PI) / 180);
        let lng = v.lng + (km / 85) * Math.sin((v.heading * Math.PI) / 180);
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
      }),
    };

    drawGrid();
    for (const site of local.sites) {
      const p = project(site.lng, site.lat);
      ctx.fillStyle = site.kind === "hub" ? "#FAF9F5" : site.kind === "charger" ? "#80AADD" : "#C2C0B6";
      ctx.beginPath();
      ctx.rect(p.x - 4, p.y - 4, 8, 8);
      ctx.fill();
      ctx.fillStyle = "rgba(250,249,245,0.7)";
      ctx.font = "11px ui-sans-serif, system-ui";
      ctx.fillText(site.name, p.x + 8, p.y + 4);
    }
    for (const v of local.vehicles) {
      const p = project(v.lng, v.lat);
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate((v.heading * Math.PI) / 180);
      ctx.fillStyle = STATUS_COLOR[v.status];
      ctx.beginPath();
      ctx.moveTo(0, -8);
      ctx.lineTo(6, 7);
      ctx.lineTo(-6, 7);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
      ctx.fillStyle = "#FAF9F5";
      ctx.font = "600 11px ui-sans-serif, system-ui";
      ctx.fillText(v.id, p.x + 8, p.y - 6);
    }
    raf = requestAnimationFrame(draw);
  };

  const hitTest = (x: number, y: number): Vehicle | undefined => {
    return local.vehicles.find((v) => {
      const p = project(v.lng, v.lat);
      return Math.hypot(p.x - x, p.y - y) < 16;
    });
  };

  canvas.addEventListener("pointerdown", (e) => {
    dragging = true;
    lastX = e.offsetX;
    lastY = e.offsetY;
    const hit = hitTest(e.offsetX, e.offsetY);
    if (hit) onSelect(hit);
  });
  canvas.addEventListener("pointerup", () => {
    dragging = false;
  });
  canvas.addEventListener("pointerleave", () => {
    dragging = false;
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    panX += e.offsetX - lastX;
    panY += e.offsetY - lastY;
    lastX = e.offsetX;
    lastY = e.offsetY;
  });
  canvas.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      const next = Math.min(2.4, Math.max(0.7, scale + (e.deltaY < 0 ? 0.08 : -0.08)));
      scale = next;
    },
    { passive: false },
  );

  const ro = new ResizeObserver(resize);
  ro.observe(canvas);
  resize();
  raf = requestAnimationFrame(draw);

  return () => {
    cancelAnimationFrame(raf);
    ro.disconnect();
  };
}
