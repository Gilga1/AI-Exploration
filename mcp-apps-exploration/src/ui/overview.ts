import { describeDimensions, type HostContext } from "../host-context.ts";
import type { PromptLauncherId } from "../prompt-copy.ts";
import type { RegionName } from "../catalog.ts";
import { renderPromptLaunchers } from "./prompt-launchers.ts";

export function renderOverview(
  root: HTMLElement,
  ctx: HostContext | undefined,
  log: string[],
  onLaunchPrompt?: (id: PromptLauncherId, region?: RegionName) => void,
) {
  const dims = ctx?.containerDimensions;
  const widthText =
    dims && "width" in dims && typeof dims.width === "number"
      ? `${dims.width}px`
      : dims && "maxWidth" in dims && dims.maxWidth != null
        ? `≤ ${dims.maxWidth}px`
        : "host-controlled";
  root.innerHTML = `
    <article class="hero card">
      <p class="eyebrow">Fleet Ops · Territory Trade analog</p>
      <h2>Connector home — not Claude Dashboards/Motion.</h2>
      <p>This MCP App is a <strong>custom connector</strong>: tools + prompts + resources + rich UI. In-app <strong>filter / refresh / drill</strong> use <code>callServerTool</code> (no Send). <strong>Explain</strong> fills the Desktop composer — you press Send.</p>
      <dl class="facts">
        <div><dt>Display mode</dt><dd id="fact-mode">${ctx?.displayMode ?? "unknown"}</dd></div>
        <div><dt>Available modes</dt><dd>${(ctx?.availableDisplayModes ?? []).join(", ") || "unknown"}</dd></div>
        <div><dt>Reported width</dt><dd id="fact-width">${widthText}</dd></div>
        <div><dt>Dimensions</dt><dd>${describeDimensions(dims)}</dd></div>
      </dl>
      <div class="actions">
        <button class="btn" data-mode="fullscreen">Request fullscreen</button>
        <button class="btn ghost" data-mode="inline">Request inline</button>
        <button class="btn ghost" data-mode="pip">Request PiP</button>
      </div>
    </article>
    <article class="card">
      <p class="eyebrow">Domain tools (chat or callServerTool)</p>
      <ul class="tight">
        <li><code>list_delayed_vans</code> — trade-today table (no UI).</li>
        <li><code>filter_fleet</code> / <code>refresh_fleet_snapshot</code> — instant UI updates from the app.</li>
        <li><code>get_vehicle_detail</code> / <code>get_region_summary</code> — drill-down.</li>
      </ul>
    </article>
    <article class="card">
      <p class="eyebrow">Claude product features</p>
      <p>Real <strong>Dashboards</strong> / <strong>Motion</strong> live in Claude Artifacts — attach <code>ops://claude-product-notes</code> or read <code>CLAUDE_PRODUCT.md</code>. The Briefing tab here is a CSS POC only.</p>
    </article>
    <article class="card">
      <p class="eyebrow">Host log</p>
      <pre class="log">${log.slice(-8).join("\n") || "Waiting for host messages…"}</pre>
    </article>
  `;
  if (onLaunchPrompt) {
    renderPromptLaunchers(root, onLaunchPrompt);
  }
}
