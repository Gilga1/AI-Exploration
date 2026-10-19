import { hourlyVolumeQueryBehind, KPI_QUERY_BEHIND, regionQueryBehind } from "../dashboard-queries.ts";
import type { Alert, FleetSnapshot } from "../mock-data.ts";
import { formatDelta, sparkPath } from "./dom.ts";

export type DashboardHandlers = {
  /** Judgment only — fills Claude composer on Desktop (press Send). */
  onExplain: (message: string, stagedContext?: string) => void;
  /** Instant — callServerTool refresh_fleet_snapshot (no Claude turn). */
  onRefresh?: () => void;
  /** Instant — callServerTool filter_fleet by region. */
  onFilterRegion?: (region: string) => void;
};

type Selection =
  | { kind: "kpi"; id: string; label: string; value: number; unit: string; query: string }
  | { kind: "region"; region: string; onTimePct: number; volume: number; incidents: number; query: string }
  | { kind: "hour"; hour: number; volume: number; query: string }
  | { kind: "alert"; alert: Alert; query: string };

export function renderDashboard(root: HTMLElement, snapshot: FleetSnapshot, handlers?: DashboardHandlers) {
  const maxVolume = Math.max(...snapshot.regions.map((r) => r.volume), 1);
  const maxHour = Math.max(...snapshot.hourlyVolume, 1);
  const refreshed = snapshot.generatedAt.slice(0, 16).replace("T", " ");
  root.innerHTML = `
    <p class="lede">Ops board: click any metric to inspect the mock query. <strong>Refresh</strong> / region chips use tools (no Send). <strong>Explain</strong> is judgment-only (Desktop: composer → Send).</p>
    <div class="actions sticky dash-toolbar">
      <button type="button" class="btn" id="dash-refresh">Refresh data</button>
      <button type="button" class="btn ghost" data-filter-region="all">All regions</button>
      ${snapshot.regions.map((r) => `<button type="button" class="btn ghost" data-filter-region="${r.region}">${r.region}</button>`).join("")}
    </div>
    <p class="caption">Snapshot ${refreshed} UTC</p>
    <div class="kpi-grid">
      ${snapshot.kpis
        .map(
          (k) => `
        <article class="card kpi dash-select" data-select="kpi" data-kpi="${k.id}" tabindex="0" role="button" aria-label="${k.label} KPI">
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
    <article class="card query-behind" id="selection-detail" hidden>
      <p class="eyebrow" id="selection-title">Selection</p>
      <p id="selection-summary"></p>
      <pre class="log" id="selection-query"></pre>
      <div class="actions">
        <button type="button" class="btn" id="selection-explain">Explain</button>
      </div>
    </article>
    <div class="split">
      <article class="card dash-select-block">
        <p class="eyebrow">Hourly volume</p>
        <div class="bars" role="list" aria-label="Hourly delivery volume">
          ${snapshot.hourlyVolume
            .map(
              (v, i) => `
            <div class="bar-col dash-select" data-select="hour" data-hour="${i + 7}" data-volume="${v}" role="listitem" tabindex="0">
              <div class="bar" style="height:${(v / maxHour) * 100}%"></div>
              <span>${i + 7}</span>
            </div>`,
            )
            .join("")}
        </div>
      </article>
      <article class="card">
        <p class="eyebrow">Regions</p>
        <table class="table table-select">
          <thead><tr><th>Area</th><th>On-time</th><th>Volume</th></tr></thead>
          <tbody>
            ${snapshot.regions
              .map(
                (r) => `
              <tr class="dash-select" data-select="region" data-region="${r.region}" data-ontime="${r.onTimePct}" data-volume="${r.volume}" data-incidents="${r.incidents}" tabindex="0" role="button">
                <td>${r.region}</td>
                <td>${r.onTimePct}%</td>
                <td>
                  <div class="meter"><i style="width:${(r.volume / maxVolume) * 100}%"></i></div>
                  <span class="caption">${r.volume} stops</span>
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
        <article class="card alert dash-select ${a.severity}" data-select="alert" data-alert-id="${a.id}" tabindex="0" role="button">
          <p class="eyebrow">${a.severity}${a.vehicleId ? ` · ${a.vehicleId}` : ""}</p>
          <h3>${a.title}</h3>
          <p>${a.body}</p>
        </article>`,
        )
        .join("")}
    </div>
  `;

  let selection: Selection | null = null;

  const panel = root.querySelector("#selection-detail") as HTMLElement;
  const titleEl = root.querySelector("#selection-title") as HTMLElement;
  const summaryEl = root.querySelector("#selection-summary") as HTMLElement;
  const queryEl = root.querySelector("#selection-query") as HTMLElement;

  const clearSelected = () => {
    root.querySelectorAll(".dash-selected").forEach((el) => el.classList.remove("dash-selected"));
  };

  const applySelection = (next: Selection) => {
    selection = next;
    clearSelected();
    titleEl.textContent =
      next.kind === "kpi"
        ? `KPI · ${next.label}`
        : next.kind === "region"
          ? `Region · ${next.region}`
          : next.kind === "hour"
            ? `Hourly volume · ${next.hour}:00`
            : `Alert · ${next.alert.title}`;
    summaryEl.textContent =
      next.kind === "kpi"
        ? `${next.value}${next.unit}`
        : next.kind === "region"
          ? `${next.onTimePct}% on-time · ${next.volume} stops · ${next.incidents} incidents`
          : next.kind === "hour"
            ? `${next.volume} stops in this hour`
            : next.alert.body;
    queryEl.textContent = next.query;
    panel.hidden = false;
    panel.scrollIntoView({ block: "nearest" });
  };

  const selectFromElement = (el: HTMLElement) => {
    const kind = el.dataset.select;
    if (kind === "kpi") {
      const id = el.dataset.kpi ?? "";
      const kpi = snapshot.kpis.find((k) => k.id === id);
      if (!kpi) return;
      el.classList.add("dash-selected");
      applySelection({
        kind: "kpi",
        id: kpi.id,
        label: kpi.label,
        value: kpi.value,
        unit: kpi.unit,
        query: KPI_QUERY_BEHIND[id] ?? `-- No mock query for ${id}`,
      });
      return;
    }
    if (kind === "region") {
      el.classList.add("dash-selected");
      const region = el.dataset.region ?? "";
      const onTimePct = Number(el.dataset.ontime ?? 0);
      const volume = Number(el.dataset.volume ?? 0);
      const incidents = Number(el.dataset.incidents ?? 0);
      applySelection({
        kind: "region",
        region,
        onTimePct,
        volume,
        incidents,
        query: regionQueryBehind(region, onTimePct, volume),
      });
      return;
    }
    if (kind === "hour") {
      el.classList.add("dash-selected");
      const hour = Number(el.dataset.hour ?? 0);
      const volume = Number(el.dataset.volume ?? 0);
      applySelection({
        kind: "hour",
        hour,
        volume,
        query: hourlyVolumeQueryBehind(hour, volume),
      });
      return;
    }
    if (kind === "alert") {
      const alert = snapshot.alerts.find((a) => a.id === el.dataset.alertId);
      if (!alert) return;
      el.classList.add("dash-selected");
      applySelection({
        kind: "alert",
        alert,
        query: `-- Ops alert (no SQL)\n-- severity: ${alert.severity}\n-- vehicle: ${alert.vehicleId ?? "n/a"}`,
      });
    }
  };

  root.querySelectorAll(".dash-select").forEach((el) => {
    el.addEventListener("click", () => selectFromElement(el as HTMLElement));
    el.addEventListener("keydown", (e) => {
      const key = (e as KeyboardEvent).key;
      if (key === "Enter" || key === " ") {
        e.preventDefault();
        selectFromElement(el as HTMLElement);
      }
    });
  });

  root.querySelector("#dash-refresh")?.addEventListener("click", () => handlers?.onRefresh?.());
  root.querySelectorAll("[data-filter-region]").forEach((btn) => {
    btn.addEventListener("click", () => {
      handlers?.onFilterRegion?.((btn as HTMLElement).dataset.filterRegion ?? "all");
    });
  });

  root.querySelector("#selection-explain")?.addEventListener("click", () => {
    if (!selection || !handlers) return;
    const staged = `${titleEl.textContent}\n\n${summaryEl.textContent}\n\n${queryEl.textContent}`;
    let message = "";
    if (selection.kind === "kpi") {
      message = `Explain the **${selection.label}** KPI (${selection.value}${selection.unit}) on the operations board.`;
    } else if (selection.kind === "region") {
      message = `Explain **${selection.region}** (${selection.onTimePct}% on-time, ${selection.volume} stops, ${selection.incidents} incidents).`;
    } else if (selection.kind === "hour") {
      message = `Explain hourly volume at **${selection.hour}:00** (${selection.volume} stops).`;
    } else {
      message = `Explain alert **${selection.alert.title}**: ${selection.alert.body}`;
    }
    handlers.onExplain(message, staged);
  });
}
