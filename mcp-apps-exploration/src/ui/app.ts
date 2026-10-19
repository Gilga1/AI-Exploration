import { App } from "@modelcontextprotocol/ext-apps";
import { FLEET_SNAPSHOT, parseSnapshot, type FleetSnapshot, type Vehicle } from "../mock-data.ts";
import { applyHostVariables, applySafeArea, VIEWS, type ViewId, $ } from "./dom.ts";
import { renderOverview } from "./overview.ts";
import { mountMap } from "./map.ts";
import { renderDashboard } from "./dashboard.ts";
import { renderMotion } from "./motion.ts";
import { promptTextForLauncher, type PromptLauncherId } from "../prompt-copy.ts";
import type { RegionName } from "../catalog.ts";
import { renderModals, vehicleSheetHtml } from "./modals.ts";
import { renderInteractions } from "./interactions.ts";
import type { HostContext } from "../host-context.ts";
import "./styles.css";

const app = new App(
  { name: "MCP Apps UX exploration", version: "0.1.0" },
  { availableDisplayModes: ["inline", "fullscreen", "pip"] },
  { autoResize: true },
);

let snapshot: FleetSnapshot = FLEET_SNAPSHOT;
let view: ViewId = "overview";
let log: string[] = [];
let stopMap: (() => void) | undefined;

function pushLog(line: string) {
  log = [...log, `${new Date().toISOString().slice(11, 19)} ${line}`].slice(-20);
}

function hostContext(): HostContext | undefined {
  return app.getHostContext() as HostContext | undefined;
}

function applyChrome() {
  const ctx = hostContext();
  document.body.classList.toggle("fullscreen", ctx?.displayMode === "fullscreen");
  document.body.dataset.theme = ctx?.theme ?? "dark";
  applyHostVariables(ctx?.styles?.variables);
  applySafeArea($("app"), ctx?.safeAreaInsets);
  $("mode-pill").textContent = `${ctx?.displayMode ?? "offline"} · ${
    ctx?.containerDimensions && "width" in ctx.containerDimensions
      ? `${(ctx.containerDimensions as { width?: number }).width ?? "?"}px`
      : "fluid width"
  }`;
}

async function sendUserMessage(text: string, stagedContext?: string) {
  const caps = app.getHostCapabilities?.() as { message?: unknown; updateModelContext?: unknown } | undefined;
  if (stagedContext && caps?.updateModelContext) {
    pushLog("updateModelContext (dashboard selection)");
    await safeHostCall("updateModelContext", () =>
      app.updateModelContext({ content: [{ type: "text", text: stagedContext }] }),
    );
  }
  if (!caps?.message) {
    pushLog("sendMessage skipped: host lacks message capability");
    return;
  }
  pushLog(`sendMessage ${text.slice(0, 60)}…`);
  await safeHostCall("sendMessage", async () => {
    const result = await app.sendMessage({ role: "user", content: [{ type: "text", text }] });
    if (result.isError) pushLog("sendMessage rejected by host");
  });
}

function render() {
  applyChrome();
  stopMap?.();
  stopMap = undefined;
  const stage = $("stage");
  const ctx = hostContext();
  if (view === "overview")
    renderOverview(stage, ctx, log, (id: PromptLauncherId, region?: RegionName) => {
      void sendUserMessage(promptTextForLauncher(id, region ?? "SOMA"));
    });
  if (view === "dashboard")
    renderDashboard(stage, snapshot, {
      onExplain: (message, stagedContext) => {
        void sendUserMessage(message, stagedContext);
      },
    });
  if (view === "motion") {
    renderMotion(stage, snapshot, (text) => {
      void sendUserMessage(text);
    });
  }
  if (view === "modals") {
    renderModals(stage, snapshot.alerts, async (kind, alert) => {
      pushLog(`modal action ${kind}`);
      if (kind === "chat") {
        await safeHostCall("sendMessage", () =>
          app.sendMessage({
            role: "user",
            content: [{ type: "text", text: `Please help with: ${alert?.title}. ${alert?.body}` }],
          }),
        );
      } else {
        await safeHostCall("updateModelContext", () =>
          app.updateModelContext({
            content: [{ type: "text", text: `User confirmed fleet action: ${kind}` }],
            structuredContent: { action: kind, alertId: alert?.id },
          }),
        );
      }
    });
  }
  if (view === "interact") {
    renderInteractions(
      stage,
      async (text) => {
        pushLog(`sendMessage ${text}`);
        await safeHostCall("sendMessage", () =>
          app.sendMessage({ role: "user", content: [{ type: "text", text }] }),
        );
      },
      async (payload) => {
        pushLog(`updateModelContext ${JSON.stringify(payload)}`);
        await safeHostCall("updateModelContext", () =>
          app.updateModelContext({
            content: [{ type: "text", text: `Filters applied: ${JSON.stringify(payload)}` }],
            structuredContent: payload,
          }),
        );
      },
    );
  }
  if (view === "map") {
    stage.innerHTML = `<div id="map-root"></div><div id="map-sheet" class="sheet" hidden></div>`;
    stopMap = mountMap($("map-root"), snapshot, (vehicle: Vehicle) => {
      const sheet = $("map-sheet");
      sheet.hidden = false;
      sheet.innerHTML = vehicleSheetHtml(vehicle);
    });
    $("map-sheet").addEventListener("click", async (e) => {
      const t = e.target as HTMLElement;
      if (t.dataset.chatVehicle) {
        await safeHostCall("sendMessage", () =>
          app.sendMessage({
            role: "user",
            content: [{ type: "text", text: `What should we do about ${t.dataset.chatVehicle}?` }],
          }),
        );
      }
    });
  }
}

function setView(next: ViewId) {
  view = next;
  document.querySelectorAll(".tabs button").forEach((btn) => {
    btn.classList.toggle("on", (btn as HTMLElement).dataset.view === view);
  });
  render();
}

document.querySelectorAll(".tabs button").forEach((btn) => {
  btn.addEventListener("click", () => setView(((btn as HTMLElement).dataset.view as ViewId) ?? "overview"));
});

$("stage").addEventListener("click", async (e) => {
  const t = e.target as HTMLElement;
  if (!t.dataset.mode) return;
  const mode = t.dataset.mode as "inline" | "fullscreen" | "pip";
  const available = hostContext()?.availableDisplayModes ?? [];
  pushLog(`requestDisplayMode ${mode} (host offers ${available.join(", ") || "none"})`);
  try {
    const result = await app.requestDisplayMode({ mode });
    pushLog(`host set mode=${result.mode}`);
    render();
  } catch (err) {
    pushLog(`display mode failed: ${err instanceof Error ? err.message : String(err)}`);
    render();
  }
});

app.onhostcontextchanged = () => {
  pushLog("host-context-changed");
  applyChrome();
  if (view === "overview") render();
};

app.ontoolinput = (params) => {
  const args = params.arguments as { view?: ViewId } | undefined;
  if (args?.view && VIEWS.some((v) => v.id === args.view)) setView(args.view);
};

app.ontoolresult = (result) => {
  const structured = (result as { structuredContent?: unknown }).structuredContent;
  snapshot = parseSnapshot(structured ?? extractJson(result));
  const text = result.content?.find((c) => c.type === "text");
  if (text && "text" in text) {
    try {
      const parsed = JSON.parse(text.text) as { view?: ViewId };
      if (parsed.view) setView(parsed.view);
    } catch {
      /* tool text is human copy */
    }
  }
  render();
};

async function safeHostCall(label: string, fn: () => Promise<unknown>) {
  try {
    await fn();
  } catch (err) {
    pushLog(`${label} skipped: ${err instanceof Error ? err.message : String(err)}`);
  }
}

function extractJson(result: { content?: Array<{ type: string; text?: string }> }): unknown {
  const block = result.content?.find((c) => c.type === "text");
  if (!block?.text) return undefined;
  try {
    return JSON.parse(block.text);
  } catch {
    return undefined;
  }
}

async function boot() {
  try {
    await app.connect();
    pushLog("connected to host via PostMessageTransport");
  } catch (err) {
    pushLog(`connect failed (${err instanceof Error ? err.message : String(err)}); UI still renders with mock data`);
  }
  render();
}

void boot();
