import { REGIONS, type RegionName } from "../catalog.ts";
import type { PromptLauncherId } from "../prompt-copy.ts";

const LAUNCHERS: {
  id: PromptLauncherId;
  title: string;
  blurb: string;
  needsRegion?: boolean;
}[] = [
  {
    id: "open_fleet_ops",
    title: "Open Fleet Ops",
    blurb: "Connector home · host inspector.",
  },
  {
    id: "delayed_vans_today",
    title: "Delayed vans today",
    blurb: "Trade-today analog · list + map.",
  },
  {
    id: "region_ops_report",
    title: "Region ops report",
    blurb: "Weekly report analog · pick region.",
    needsRegion: true,
  },
  {
    id: "incident_playbook",
    title: "Incident playbook",
    blurb: "Sheets · confirm in-app.",
  },
  {
    id: "open_ops_board",
    title: "Ops board walkthrough",
    blurb: "KPI board (not Claude Dashboards).",
  },
  {
    id: "fleet_briefing_story",
    title: "Briefing story",
    blurb: "CSS scene (not Claude Motion).",
  },
];

export function renderPromptLaunchers(
  root: HTMLElement,
  onLaunch: (id: PromptLauncherId, region?: RegionName) => void,
) {
  const host = document.createElement("article");
  host.className = "card";
  host.innerHTML = `
    <p class="eyebrow">Recipes (fill composer)</p>
    <p>Same text as <strong>+ → Connectors</strong> prompts. On Claude Desktop, <code>sendMessage</code> only fills the composer — press <strong>Send</strong>.</p>
    <div class="prompt-grid" role="list"></div>
    <p class="caption">Filters / refresh / drill-down use <code>callServerTool</code> and do <em>not</em> need Send.</p>
  `;
  const grid = host.querySelector(".prompt-grid") as HTMLElement;

  for (const item of LAUNCHERS) {
    const row = document.createElement("div");
    row.className = "prompt-row";
    row.setAttribute("role", "listitem");
    if (item.needsRegion) {
      row.innerHTML = `
        <div>
          <strong>${item.title}</strong>
          <p class="caption">${item.blurb}</p>
        </div>
        <div class="prompt-actions">
          <select class="prompt-region" aria-label="Region for report">
            ${REGIONS.map((r) => `<option value="${r}">${r}</option>`).join("")}
          </select>
          <button class="btn" data-prompt="${item.id}">Run now</button>
        </div>
      `;
    } else {
      row.innerHTML = `
        <div>
          <strong>${item.title}</strong>
          <p class="caption">${item.blurb}</p>
        </div>
        <button class="btn" data-prompt="${item.id}">Run now</button>
      `;
    }
    grid.appendChild(row);
  }

  host.addEventListener("click", (e) => {
    const btn = (e.target as HTMLElement).closest("[data-prompt]") as HTMLElement | null;
    if (!btn) return;
    const id = btn.dataset.prompt as PromptLauncherId;
    const regionSelect = btn.closest(".prompt-row")?.querySelector(".prompt-region") as HTMLSelectElement | null;
    onLaunch(id, regionSelect?.value as RegionName | undefined);
  });

  root.appendChild(host);
}
