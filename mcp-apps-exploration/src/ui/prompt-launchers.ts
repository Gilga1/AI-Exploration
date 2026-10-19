import { REGIONS, type RegionName } from "../catalog.ts";
import type { PromptLauncherId } from "../prompt-copy.ts";

const LAUNCHERS: {
  id: PromptLauncherId;
  title: string;
  blurb: string;
  needsRegion?: boolean;
}[] = [
  {
    id: "open_gallery",
    title: "Open gallery",
    blurb: "Host inspector + offer map or dashboard.",
  },
  {
    id: "delayed_vans_today",
    title: "Delayed vans today",
    blurb: "Trade-today analog · opens live map.",
  },
  {
    id: "region_ops_report",
    title: "Region ops report",
    blurb: "Parameterized weekly-style report.",
    needsRegion: true,
  },
  {
    id: "incident_playbook",
    title: "Incident playbook",
    blurb: "Sheets view + critical alert walkthrough.",
  },
  {
    id: "open_ops_dashboard",
    title: "Claude Dashboard-style",
    blurb: "KPI dashboard with query transparency.",
  },
  {
    id: "animate_fleet_briefing",
    title: "Claude Motion-style",
    blurb: "30s code-built fleet explainer.",
  },
];

export function renderPromptLaunchers(
  root: HTMLElement,
  onLaunch: (id: PromptLauncherId, region?: RegionName) => void,
) {
  const host = document.createElement("article");
  host.className = "card";
  host.innerHTML = `
    <p class="eyebrow">Run in Claude (instant)</p>
    <p>These buttons call <code>ui/message</code> with the same recipes as the <strong>+ → Connectors</strong> prompts — no extra “go” step.</p>
    <div class="prompt-grid" role="list"></div>
    <p class="caption">Resources (<code>ops://glossary</code>, etc.) still attach from the + menu for grounding.</p>
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
