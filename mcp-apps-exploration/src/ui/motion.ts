import type { FleetSnapshot } from "../mock-data.ts";

export function renderMotion(root: HTMLElement, snapshot: FleetSnapshot, onAsk: (text: string) => void) {
  const onTime = snapshot.kpis.find((k) => k.id === "ontime")?.value ?? 94;
  const delayed = snapshot.vehicles.filter((v) => v.status === "delayed").length;
  const critical = snapshot.alerts.filter((a) => a.severity === "critical").length;

  root.innerHTML = `
    <p class="lede"><strong>POC briefing only</strong> — CSS in this iframe. This is <em>not</em> Claude Motion (no MP4 export). For real Motion, use Claude Artifacts — see <code>CLAUDE_PRODUCT.md</code>.</p>
    <article class="card motion-stage" aria-label="Fleet briefing scene">
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
      <p class="caption">Mock snapshot ${snapshot.generatedAt.slice(0, 16).replace("T", " ")} UTC</p>
    </article>
    <div class="actions">
      <button class="btn" id="motion-ask">Ask Claude to narrate (composer)</button>
    </div>
  `;

  root.querySelector("#motion-ask")?.addEventListener("click", () => {
    onAsk(
      "Narrate this fleet briefing scene: on-time trend, delayed vans, critical dock hold. Keep the app on the briefing view. Remind me this is not Claude Motion MP4.",
    );
  });
}
