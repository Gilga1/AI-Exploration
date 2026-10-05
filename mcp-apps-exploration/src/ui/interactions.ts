export function renderInteractions(
  root: HTMLElement,
  onMessage: (text: string) => void,
  onContext: (payload: Record<string, unknown>) => void,
) {
  root.innerHTML = `
    <p class="lede">Direct manipulation belongs in the app. Language and judgment belong in chat. These controls are the ones Claude's guidelines call out as native: segmented buttons, sliders, toggles, and carousels.</p>
    <article class="card">
      <p class="eyebrow">Horizon</p>
      <div class="segmented" role="tablist">
        <button class="seg on" data-horizon="today">Today</button>
        <button class="seg" data-horizon="week">This week</button>
        <button class="seg" data-horizon="month">Month</button>
      </div>
    </article>
    <article class="card">
      <p class="eyebrow">SLA threshold</p>
      <label class="field">On-time target
        <input id="sla" type="range" min="80" max="99" value="94" />
      </label>
      <p id="sla-label" class="caption">94%</p>
    </article>
    <article class="card">
      <p class="eyebrow">Live overlay</p>
      <label class="toggle"><input id="live" type="checkbox" checked /> Stream vehicle positions</label>
      <label class="toggle"><input id="heat" type="checkbox" /> Show delay heatmap</label>
    </article>
    <article class="card">
      <p class="eyebrow">Carousel</p>
      <div class="carousel" tabindex="0">
        ${["SoMa Hub", "Marina Hub", "Mission Plaza", "Ferry Building"]
          .map(
            (name, i) => `
          <button class="carousel-card" data-place="${name}">
            <span class="eyebrow">Stop ${i + 1}</span>
            <strong>${name}</strong>
            <span class="caption">Tap to inspect</span>
          </button>`,
          )
          .join("")}
      </div>
    </article>
    <div class="actions sticky">
      <button class="btn" id="apply">Apply filters to model context</button>
      <button class="btn ghost" id="ask">Ask Claude to explain outliers</button>
    </div>
  `;

  const state = { horizon: "today", sla: 94, live: true, heat: false, place: "SoMa Hub" };

  root.querySelectorAll(".seg").forEach((btn) => {
    btn.addEventListener("click", () => {
      root.querySelectorAll(".seg").forEach((b) => b.classList.remove("on"));
      btn.classList.add("on");
      state.horizon = (btn as HTMLElement).dataset.horizon ?? "today";
    });
  });
  const sla = root.querySelector("#sla") as HTMLInputElement;
  const slaLabel = root.querySelector("#sla-label") as HTMLElement;
  sla.addEventListener("input", () => {
    state.sla = Number(sla.value);
    slaLabel.textContent = `${state.sla}%`;
  });
  (root.querySelector("#live") as HTMLInputElement).addEventListener("change", (e) => {
    state.live = (e.target as HTMLInputElement).checked;
  });
  (root.querySelector("#heat") as HTMLInputElement).addEventListener("change", (e) => {
    state.heat = (e.target as HTMLInputElement).checked;
  });
  root.querySelectorAll("[data-place]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.place = (btn as HTMLElement).dataset.place ?? state.place;
      onMessage(`Focus the fleet view on ${state.place}.`);
    });
  });
  root.querySelector("#apply")?.addEventListener("click", () => onContext(state));
  root.querySelector("#ask")?.addEventListener("click", () => {
    onMessage(
      `Explain outliers for horizon=${state.horizon}, SLA=${state.sla}%, live=${state.live}, heatmap=${state.heat}.`,
    );
  });
}
