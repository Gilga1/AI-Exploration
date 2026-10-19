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
  { name: "Fleet Ops", version: "0.2.0" },
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

/** Judgment path — Desktop only fills composer; user must Send. */
async function sendUserMessage(text: string, stagedContext?: string) {
  const caps = app.getHostCapabilities();
  if (stagedContext && caps?.updateModelContext) {
    pushLog("updateModelContext (selection)");
    await safeHostCall("updateModelContext", () =>
      app.updateModelContext({ content: [{ type: "text", text: stagedContext }] }),
    );
  }
  if (!caps?.message) {
    pushLog("sendMessage skipped: host lacks message capability");
    return;
  }
  pushLog(`sendMessage → composer ${text.slice(0, 48)}…`);
  await safeHostCall("sendMessage", async () => {
    const result = await app.sendMessage({ role: "user", content: [{ type: "text", text }] });
    if (result.isError) pushLog("sendMessage rejected by host");
  });
}

/** Instant path — no Claude turn. */
async function callTool(name: string, args: Record<string, unknown> = {}) {
  pushLog(`callServerTool ${name} ${JSON.stringify(args)}`);
  const caps = app.getHostCapabilities();
  if (!caps?.serverTools) {
    pushLog("callServerTool skipped: host lacks serverTools");
    return;
  }
  await safeHostCall("callServerTool", async () => {
    const result = await app.callServerTool({ name, arguments: args });
    applyToolPayload(result);
  });
}

function applyToolPayload(result: {
  content?: Array<{ type: string; text?: string }>;
  structuredContent?: unknown;
}) {
  const structured = result.structuredContent as
    | (Partial<FleetSnapshot> & {
        view?: ViewId;
        focusVehicleId?: string;
        vehicleDetail?: {
          found: boolean;
          vehicle?: Vehicle;
          region?: string;
          alerts?: Array<{ title: string; body: string }>;
        };
      })
    | undefined;

  if (structured?.vehicleDetail && !Array.isArray(structured.vehicles)) {
    const sheet = document.getElementById("map-sheet");
    const d = structured.vehicleDetail;
    if (sheet && d.found && d.vehicle) {
      sheet.hidden = false;
      sheet.innerHTML = `${vehicleSheetHtml(d.vehicle)}
        <p class="caption">Region: ${d.region ?? "—"} · alerts: ${d.alerts?.length ?? 0}</p>
        <pre class="log">${JSON.stringify(d, null, 2)}</pre>
        <div class="actions">
          <button type="button" class="btn ghost" data-chat-vehicle="${d.vehicle.id}">Ask Claude (composer)</button>
        </div>`;
    }
    pushLog(`vehicle detail ${structured.focusVehicleId ?? ""}`);
    return;
  }

  if (structured && Array.isArray(structured.vehicles)) {
    snapshot = parseSnapshot(structured);
  }
  if (structured?.view && VIEWS.some((v) => v.id === structured.view)) {
    view = structured.view;
    document.querySelectorAll(".tabs button").forEach((btn) => {
      btn.classList.toggle("on", (btn as HTMLElement).dataset.view === view);
    });
  }
  render();
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
      onRefresh: () => {
        void callTool("refresh_fleet_snapshot");
      },
      onFilterRegion: (region) => {
        void callTool("filter_fleet", {
          region,
          status: "all",
          view: "dashboard",
        });
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
        await sendUserMessage(`Please help with: ${alert?.title}. ${alert?.body}`);
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
    renderInteractions(stage, {
      onApplyFilters: (payload) => {
        void callTool("filter_fleet", {
          status: payload.status,
          region: "all",
          sla_target: payload.sla,
          view: "map",
        });
      },
      onAskClaude: (text) => {
        void sendUserMessage(text);
      },
    });
  }
  if (view === "map") {
    stage.innerHTML = `
      <div class="actions sticky map-toolbar">
        <button type="button" class="btn ghost" data-map-filter="all">All</button>
        <button type="button" class="btn ghost" data-map-filter="delayed">Delayed</button>
        <button type="button" class="btn ghost" data-map-filter="en_route">En route</button>
        <button type="button" class="btn" data-map-refresh>Refresh</button>
      </div>
      <div id="map-root"></div>
      <div id="map-sheet" class="sheet" hidden></div>`;
    stage.querySelector("[data-map-refresh]")?.addEventListener("click", () => {
      void callTool("refresh_fleet_snapshot");
    });
    stage.querySelectorAll("[data-map-filter]").forEach((btn) => {
      btn.addEventListener("click", () => {
        void callTool("filter_fleet", {
          status: (btn as HTMLElement).dataset.mapFilter ?? "all",
          region: "all",
          view: "map",
        });
      });
    });
    stopMap = mountMap($("map-root"), snapshot, (vehicle: Vehicle) => {
      const sheet = $("map-sheet");
      sheet.hidden = false;
      sheet.innerHTML = `${vehicleSheetHtml(vehicle)}
        <div class="actions">
          <button type="button" class="btn" data-drill="${vehicle.id}">Server detail (no Claude)</button>
        </div>`;
    });
    $("map-sheet").addEventListener("click", async (e) => {
      const t = e.target as HTMLElement;
      if (t.dataset.drill) {
        await callTool("get_vehicle_detail", { vehicle_id: t.dataset.drill });
        return;
      }
      if (t.dataset.chatVehicle) {
        await sendUserMessage(`What should we do about ${t.dataset.chatVehicle}?`);
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
  applyToolPayload(result as { content?: Array<{ type: string; text?: string }>; structuredContent?: unknown });
};

async function safeHostCall(label: string, fn: () => Promise<unknown>) {
  try {
    await fn();
  } catch (err) {
    pushLog(`${label} skipped: ${err instanceof Error ? err.message : String(err)}`);
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
