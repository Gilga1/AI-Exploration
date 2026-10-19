import { KPI_QUERY_BEHIND } from "../dashboard-queries.ts";
import type { FleetSnapshot } from "../mock-data.ts";
import { formatDelta, sparkPath } from "./dom.ts";

export type DashboardHandlers = {
  onExplainKpi: (kpiId: string, label: string, value: number, unit: string) => void;
  onExplainRegion: (region: string, onTimePct: number) => void;
};

export function renderDashboard(root: HTMLElement, snapshot: FleetSnapshot, handlers?: DashboardHandlers) {
  const maxVolume = Math.max(...snapshot.regions.map((r) => r.volume), 1);
  const maxHour = Math.max(...snapshot.hourlyVolume, 1);
  const refreshed = snapshot.generatedAt.slice(0, 16).replace("T", " ");
  root.innerHTML = `
    <p class="lede">Claude Dashboards pattern: click a KPI to see the <strong>mock query</strong> behind it, then ask Claude to explain or change the chart.</p>
    <p class="caption">Data refreshed ${refreshed} UTC (mock snapshot)</p>
    <div class="kpi-grid">
      ${snapshot.kpis
        .map(
          (k) => `
        <article class="card kpi kpi-click" data-kpi="${k.id}" tabindex="0" role="button">
          <p class="eyebrow">${k.label}</p>
          <p class="kpi-value">${k.value}${k.unit ? `<span>${k.unit}</span>` : ""}</p>
          <p class="delta ${k.deltaPct >= 0 ? "up" : "down"}">${formatDelta(k.deltaPct)}</p>
          <svg viewBox="0 0 120 28" class="spark" aria-hidden="true">
            <path d="${sparkPath(k.spark, 120, 28)}" fill="none" stroke="currentColor" stroke-width="2"/>
          </svg>
          <p class="caption">Click for query</p>
        </article>`,
        )
        .join("")}
    </div>
    <article class="card query-behind" id="query-behind" hidden>
      <p class="eyebrow">Query behind this number</p>
      <pre class="log" id="query-text"></pre>
      <div class="actions">
        <button class="btn" id="query-explain">Ask Claude to explain</button>
      </div>
    </article>
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
          <thead><tr><th>Area</th><th>On-time</th><th>Volume</th><th></th></tr></thead>
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
                <td><button class="btn ghost btn-sm" data-region="${r.region}" data-ontime="${r.onTimePct}">Ask</button></td>
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

  let activeKpi: { id: string; label: string; value: number; unit: string } | null = null;

  const showQuery = (kpiId: string) => {
    const kpi = snapshot.kpis.find((k) => k.id === kpiId);
    if (!kpi) return;
    activeKpi = { id: kpi.id, label: kpi.label, value: kpi.value, unit: kpi.unit };
    const panel = root.querySelector("#query-behind") as HTMLElement;
    const pre = root.querySelector("#query-text") as HTMLElement;
    pre.textContent = KPI_QUERY_BEHIND[kpiId] ?? `-- No mock query for ${kpiId}`;
    panel.hidden = false;
    panel.scrollIntoView({ block: "nearest" });
  };

  root.querySelectorAll(".kpi-click").forEach((el) => {
    el.addEventListener("click", () => showQuery((el as HTMLElement).dataset.kpi ?? ""));
    el.addEventListener("keydown", (e) => {
      const key = (e as KeyboardEvent).key;
      if (key === "Enter" || key === " ") {
        e.preventDefault();
        showQuery((el as HTMLElement).dataset.kpi ?? "");
      }
    });
  });

  root.querySelector("#query-explain")?.addEventListener("click", () => {
    if (!activeKpi || !handlers) return;
    handlers.onExplainKpi(activeKpi.id, activeKpi.label, activeKpi.value, activeKpi.unit);
  });

  root.querySelectorAll("[data-region]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!handlers) return;
      const el = btn as HTMLElement;
      handlers.onExplainRegion(el.dataset.region ?? "", Number(el.dataset.ontime ?? 0));
    });
  });
}
