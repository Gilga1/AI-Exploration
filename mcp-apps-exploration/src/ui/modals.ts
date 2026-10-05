import type { Alert, Vehicle } from "../mock-data.ts";

export type OverlayKind = "sheet" | "dialog" | "none";

export function renderModals(
  root: HTMLElement,
  alerts: Alert[],
  onAction: (kind: string, alert?: Alert) => void,
) {
  root.innerHTML = `
    <p class="lede">Claude's design guidelines prefer visible controls over menus, and fullscreen over nested overlays. These patterns stay inside the iframe so they never try to escape the sandbox.</p>
    <div class="pattern-grid">
      <article class="card">
        <p class="eyebrow">Recommended</p>
        <h3>Bottom sheet</h3>
        <p>In-flow panel that grows the card height. Survives inline clipping and works with auto-resize.</p>
        <button class="btn" data-open="sheet">Open reroute sheet</button>
      </article>
      <article class="card">
        <p class="eyebrow">Use with care</p>
        <h3>In-iframe dialog</h3>
        <p>Possible, but Claude warns floating panels can clip against the host. Best after requesting fullscreen.</p>
        <button class="btn ghost" data-open="dialog">Open confirm dialog</button>
      </article>
      <article class="card">
        <p class="eyebrow">Best for chat</p>
        <h3>Send to Claude</h3>
        <p>Hand language-heavy decisions back to the composer via <code>ui/message</code>.</p>
        <button class="btn ghost" data-open="chat">Ask Claude to reroute</button>
      </article>
    </div>
    <div class="alert-list">
      ${alerts
        .map(
          (a) => `
        <article class="card alert ${a.severity}">
          <p class="eyebrow">${a.severity}</p>
          <h3>${a.title}</h3>
          <p>${a.body}</p>
          <div class="actions">
            <button class="btn" data-sheet="${a.id}">Inspect</button>
            <button class="btn ghost" data-chat="${a.id}">Discuss</button>
          </div>
        </article>`,
        )
        .join("")}
    </div>
    <div id="sheet" class="sheet" hidden>
      <div class="sheet-handle"></div>
      <div id="sheet-body"></div>
    </div>
    <div id="dialog-root" class="dialog-root" hidden>
      <div class="dialog" role="dialog" aria-modal="true">
        <div id="dialog-body"></div>
      </div>
    </div>
  `;

  const sheet = root.querySelector("#sheet") as HTMLElement;
  const sheetBody = root.querySelector("#sheet-body") as HTMLElement;
  const dialogRoot = root.querySelector("#dialog-root") as HTMLElement;
  const dialogBody = root.querySelector("#dialog-body") as HTMLElement;

  const fillSheet = (alert = alerts[0]) => {
    sheetBody.innerHTML = `
      <p class="eyebrow">Reroute</p>
      <h3>${alert.title}</h3>
      <p>${alert.body}</p>
      <label class="field">Hold at hub
        <input type="range" min="0" max="40" value="12" />
      </label>
      <div class="actions">
        <button class="btn" data-confirm="hold">Hold 12 min</button>
        <button class="btn ghost" data-close="sheet">Cancel</button>
      </div>
    `;
    sheet.hidden = false;
  };

  const fillDialog = (alert = alerts.find((a) => a.severity === "critical") ?? alerts[0]) => {
    dialogBody.innerHTML = `
      <p class="eyebrow">Confirm</p>
      <h3>Release ${alert.vehicleId ?? "van"} to customer dock?</h3>
      <p>This stays inside the iframe. If the host clips overflow, request fullscreen first.</p>
      <div class="actions">
        <button class="btn" data-confirm="release">Confirm</button>
        <button class="btn ghost" data-close="dialog">Keep holding</button>
      </div>
    `;
    dialogRoot.hidden = false;
  };

  root.addEventListener("click", (e) => {
    const t = e.target as HTMLElement;
    if (t.dataset.open === "sheet" || t.dataset.sheet) fillSheet(alerts.find((a) => a.id === t.dataset.sheet) ?? alerts[0]);
    if (t.dataset.open === "dialog") fillDialog();
    if (t.dataset.open === "chat" || t.dataset.chat) {
      const alert = alerts.find((a) => a.id === t.dataset.chat) ?? alerts[2] ?? alerts[0];
      onAction("chat", alert);
    }
    if (t.dataset.close === "sheet") sheet.hidden = true;
    if (t.dataset.close === "dialog") dialogRoot.hidden = true;
    if (t.dataset.confirm) {
      onAction(t.dataset.confirm, alerts[0]);
      sheet.hidden = true;
      dialogRoot.hidden = true;
    }
  });
}

export function vehicleSheetHtml(v: Vehicle): string {
  return `
    <p class="eyebrow">${v.status.replace("_", " ")}</p>
    <h3>${v.id} · ${v.driver}</h3>
    <p>Load: ${v.load}. Speed ${v.speedKph} kph. ETA ${v.etaMin} min.</p>
    <div class="actions">
      <button class="btn" data-focus="${v.id}">Keep tracking</button>
      <button class="btn ghost" data-chat-vehicle="${v.id}">Ask Claude</button>
    </div>
  `;
}
