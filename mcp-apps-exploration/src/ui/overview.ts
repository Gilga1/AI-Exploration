import { describeDimensions, type HostContext } from "../host-context.ts";

export function renderOverview(root: HTMLElement, ctx: HostContext | undefined, log: string[]) {
  const dims = ctx?.containerDimensions;
  const widthText =
    dims && "width" in dims && typeof dims.width === "number"
      ? `${dims.width}px`
      : dims && "maxWidth" in dims && dims.maxWidth != null
        ? `≤ ${dims.maxWidth}px`
        : "host-controlled";
  root.innerHTML = `
    <article class="hero card">
      <p class="eyebrow">Width is not a protocol constant</p>
      <h2>This app fills its host container.</h2>
      <p>The screenshot of Claude's chat column is the <em>inline</em> host layout, not an MCP Apps maximum. The spec gives the host <code>containerDimensions.width</code> or <code>maxWidth</code>, plus <code>inline</code>, <code>fullscreen</code>, and <code>pip</code>.</p>
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
      <p class="caption">Hosts may refuse a mode. Claude currently advertises inline + fullscreen; PiP is in the spec and SDK but is not offered on claude.ai yet.</p>
    </article>
    <article class="card">
      <p class="eyebrow">What MCP Apps can do</p>
      <ul class="tight">
        <li>Render sandboxed HTML with bidirectional JSON-RPC.</li>
        <li>Call server tools, send chat messages, and update model context.</li>
        <li>Open links, download files, and optionally sample the host LLM.</li>
        <li>Theme from host CSS variables so the UI matches Claude.</li>
        <li>Load maps/tiles only after declaring CSP <code>connectDomains</code> / <code>resourceDomains</code>.</li>
      </ul>
    </article>
    <article class="card">
      <p class="eyebrow">Host log</p>
      <pre class="log">${log.slice(-8).join("\n") || "Waiting for host messages…"}</pre>
    </article>
  `;
}
