import type { FleetSnapshot } from "../mock-data.ts";
import { formatDelta, sparkPath } from "./dom.ts";

export function renderDashboard(root: HTMLElement, snapshot: FleetSnapshot) {
  const maxVolume = Math.max(...snapshot.regions.map((r) => r.volume), 1);
  const maxHour = Math.max(...snapshot.hourlyVolume, 1);
  root.innerHTML = `
    <div class="kpi-grid">
      ${snapshot.kpis
        .map(
          (k) => `
        <article class="card kpi">
          <p class="eyebrow">${k.label}</p>
          <p class="kpi-value">${k.value}${k.unit ? `<span>${k.unit}</span>` : ""}</p>
          <p class="delta ${k.deltaPct >= 0 ? "up" : "down"}">${formatDelta(k.deltaPct)}</p>
          <svg viewBox="0 0 120 28" class="spark" aria-hidden="true">
            <path d="${sparkPath(k.spark, 120, 28)}" fill="none" stroke="currentColor" stroke-width="2"/>
          </svg>
        </article>`,
        )
        .join("")}
    </div>
    <div class="split">
      <article class="card">
        <p class="eyebrow">Hourly volume</p>
        <div class="bars" role="img" aria-label="Hourly delivery volume">
          ${snapshot.hourlyVolume
            .map(
              (v, i) => `
            <div class="bar-col">
              <div class="bar" style="height:${(v / maxHour) * 100}%"></div>
              <span>${i + 7}</span>
            </div>`,
            )
            .join("")}
        </div>
      </article>
      <article class="card">
        <p class="eyebrow">Regions</p>
        <table class="table">
          <thead><tr><th>Area</th><th>On-time</th><th>Volume</th></tr></thead>
          <tbody>
            ${snapshot.regions
              .map(
                (r) => `
              <tr>
                <td>${r.region}</td>
                <td>${r.onTimePct}%</td>
                <td>
                  <div class="meter"><i style="width:${(r.volume / maxVolume) * 100}%"></i></div>
                </td>
              </tr>`,
              )
              .join("")}
          </tbody>
        </table>
      </article>
    </div>
    <div class="alert-list">
      ${snapshot.alerts
        .map(
          (a) => `
        <article class="card alert ${a.severity}">
          <p class="eyebrow">${a.severity}${a.vehicleId ? ` · ${a.vehicleId}` : ""}</p>
          <h3>${a.title}</h3>
          <p>${a.body}</p>
        </article>`,
        )
        .join("")}
    </div>
  `;
}
