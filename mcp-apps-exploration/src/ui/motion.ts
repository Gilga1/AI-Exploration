import type { FleetSnapshot } from "../mock-data.ts";

export function renderMotion(root: HTMLElement, snapshot: FleetSnapshot, onAsk: (text: string) => void) {
  const onTime = snapshot.kpis.find((k) => k.id === "ontime")?.value ?? 94;
  const delayed = snapshot.vehicles.filter((v) => v.status === "delayed").length;
  const critical = snapshot.alerts.filter((a) => a.severity === "critical").length;

  root.innerHTML = `
    <p class="lede">Claude Motion builds explainers as <strong>editable code</strong> in the artifact — not generated video. This mock plays a 30-second fleet briefing with text, bars, and van markers you can hand off to Claude.</p>
    <article class="card motion-stage" aria-label="Fleet motion explainer">
      <div class="motion-scene">
        <p class="motion-title">Today's fleet pulse</p>
        <p class="motion-stat" data-step="1"><span class="motion-num">${onTime}%</span> on-time citywide</p>
        <p class="motion-stat" data-step="2"><span class="motion-num">${delayed}</span> vans delayed</p>
        <p class="motion-stat" data-step="3"><span class="motion-num">${critical}</span> critical holds</p>
        <div class="motion-track" aria-hidden="true">
          <span class="motion-van v1"></span>
          <span class="motion-van v2"></span>
          <span class="motion-van v3"></span>
        </div>
        <div class="motion-bars" aria-hidden="true">
          ${snapshot.hourlyVolume
            .slice(0, 6)
            .map((v, i) => `<span class="motion-bar" style="--h:${Math.round((v / 40) * 100)}%; --d:${i * 0.4}s"></span>`)
            .join("")}
        </div>
      </div>
      <p class="caption">Refreshed from snapshot ${snapshot.generatedAt.slice(0, 16).replace("T", " ")} UTC · MP4 export is a host feature; here we preview in CSS.</p>
    </article>
    <div class="actions">
      <button class="btn" id="motion-ask">Ask Claude to rewrite this explainer</button>
      <button class="btn ghost" id="motion-dashboard">Jump to dashboard KPIs</button>
    </div>
  `;

  root.querySelector("#motion-ask")?.addEventListener("click", () => {
    onAsk(
      "Rewrite the fleet motion explainer: shorter copy, emphasize Mission delays, and suggest one reroute. Keep the MCP App on the motion view.",
    );
  });
  root.querySelector("#motion-dashboard")?.addEventListener("click", () => {
    onAsk("Open the operations dashboard and compare Mission on-time to the city average.");
  });
}
