export type FilterPayload = {
  horizon: string;
  sla: number;
  live: boolean;
  heat: boolean;
  place: string;
  status: string;
};

export type InteractionHandlers = {
  /** callServerTool filter_fleet — no Claude turn. */
  onApplyFilters: (payload: FilterPayload) => void;
  /** Judgment — composer + Send on Desktop. */
  onAskClaude: (text: string) => void;
};

export function renderInteractions(root: HTMLElement, handlers: InteractionHandlers) {
  root.innerHTML = `
    <p class="lede"><strong>Apply filters</strong> hits the server via <code>callServerTool</code> (instant). <strong>Ask Claude</strong> is for judgment only and fills the Desktop composer.</p>
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
      <p class="eyebrow">Status filter (instant)</p>
      <div class="segmented">
        <button class="seg on" data-status="all">All</button>
        <button class="seg" data-status="delayed">Delayed</button>
        <button class="seg" data-status="en_route">En route</button>
        <button class="seg" data-status="charging">Charging</button>
      </div>
    </article>
    <article class="card">
      <p class="eyebrow">Hub focus</p>
      <div class="carousel" tabindex="0">
        ${["SoMa Hub", "Marina Hub", "Mission Plaza", "Ferry Building"]
          .map(
            (name, i) => `
          <button class="carousel-card" data-place="${name}">
            <span class="eyebrow">Stop ${i + 1}</span>
            <strong>${name}</strong>
            <span class="caption">Apply filter</span>
          </button>`,
          )
          .join("")}
      </div>
    </article>
    <div class="actions sticky">
      <button class="btn" id="apply">Apply filters (no Claude)</button>
      <button class="btn ghost" id="ask">Ask Claude about outliers</button>
    </div>
  `;

  const state = {
    horizon: "today",
    sla: 94,
    live: true,
    heat: false,
    place: "SoMa Hub",
    status: "all",
  };

  root.querySelectorAll(".seg[data-horizon]").forEach((btn) => {
    btn.addEventListener("click", () => {
      root.querySelectorAll(".seg[data-horizon]").forEach((b) => b.classList.remove("on"));
      btn.classList.add("on");
      state.horizon = (btn as HTMLElement).dataset.horizon ?? "today";
    });
  });
  root.querySelectorAll(".seg[data-status]").forEach((btn) => {
    btn.addEventListener("click", () => {
      root.querySelectorAll(".seg[data-status]").forEach((b) => b.classList.remove("on"));
      btn.classList.add("on");
      state.status = (btn as HTMLElement).dataset.status ?? "all";
      handlers.onApplyFilters({ ...state });
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
      handlers.onApplyFilters({ ...state });
    });
  });
  root.querySelector("#apply")?.addEventListener("click", () => handlers.onApplyFilters({ ...state }));
  root.querySelector("#ask")?.addEventListener("click", () => {
    handlers.onAskClaude(
      `Explain outliers for horizon=${state.horizon}, SLA=${state.sla}%, status=${state.status}, place=${state.place}.`,
    );
  });
}
