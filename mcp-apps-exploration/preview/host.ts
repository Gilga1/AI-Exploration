import { FLEET_SNAPSHOT } from "../src/mock-data.ts";
import { CLAUDE_STYLE_VARS } from "./tokens.ts";

type DisplayMode = "inline" | "fullscreen" | "pip";

const iframe = document.getElementById("app-frame") as HTMLIFrameElement;
const stage = document.getElementById("stage") as HTMLElement;
const widthEl = document.getElementById("host-width") as HTMLElement;
const modeEl = document.getElementById("host-mode") as HTMLElement;
const rpcEl = document.getElementById("last-rpc") as HTMLElement;
const preset = document.getElementById("preset") as HTMLSelectElement;
const themeSel = document.getElementById("theme") as HTMLSelectElement;

let mode: DisplayMode = "inline";
let theme: "light" | "dark" = "dark";

function currentWidth(): number {
  if (mode === "fullscreen") return Math.round(stage.getBoundingClientRect().width);
  if (mode === "pip") return 380;
  if (preset.value === "100%") return Math.round(stage.getBoundingClientRect().width);
  return Number(preset.value);
}

function hostContext() {
  return {
    theme,
    platform: "web" as const,
    displayMode: mode,
    availableDisplayModes: ["inline", "fullscreen", "pip"] as DisplayMode[],
    containerDimensions: {
      width: currentWidth(),
      maxHeight: mode === "fullscreen" ? 5000 : 900,
    },
    locale: "en-US",
    timeZone: "America/Los_Angeles",
    deviceCapabilities: { touch: false, hover: true },
    safeAreaInsets: { top: 8, right: 8, bottom: 16, left: 8 },
    styles: { variables: CLAUDE_STYLE_VARS[theme] },
  };
}

function reply(source: MessageEventSource | null, id: unknown, result: unknown) {
  (source as Window | null)?.postMessage({ jsonrpc: "2.0", id, result }, "*");
}

function notify(source: MessageEventSource | null, method: string, params: unknown) {
  (source as Window | null)?.postMessage({ jsonrpc: "2.0", method, params }, "*");
}

function applyStage() {
  stage.classList.remove("inline", "fullscreen", "pip");
  stage.classList.add(mode);
  if (mode === "inline") {
    stage.style.width = preset.value === "100%" ? "100%" : `${preset.value}px`;
  } else {
    stage.style.width = "";
  }
  widthEl.textContent = `${currentWidth()}px`;
  modeEl.textContent = mode;
  const win = iframe.contentWindow;
  if (win) {
    notify(win, "ui/notifications/host-context-changed", hostContext());
  }
}

window.addEventListener("message", (event) => {
  const msg = event.data as {
    jsonrpc?: string;
    id?: unknown;
    method?: string;
    params?: Record<string, unknown>;
  };
  if (msg?.jsonrpc !== "2.0" || !msg.method) return;
  rpcEl.textContent = msg.method;
  if (msg.method === "ui/initialize") {
    reply(event.source, msg.id, {
      protocolVersion: "2026-01-26",
      hostInfo: { name: "mcp-apps-exploration-preview", version: "0.1.0" },
      hostCapabilities: {
        openLinks: {},
        downloadFile: {},
        serverTools: {},
        logging: {},
        updateModelContext: { text: {}, structuredContent: {} },
        message: { text: {} },
      },
      hostContext: hostContext(),
    });
    const view = new URLSearchParams(location.search).get("view") ?? "overview";
    notify(event.source, "ui/notifications/tool-result", {
      content: [{ type: "text", text: JSON.stringify({ view }) }],
      structuredContent: { ...FLEET_SNAPSHOT, view },
    });
    return;
  }
  if (msg.method === "ui/request-display-mode") {
    const requested = msg.params?.mode as DisplayMode;
    if (["inline", "fullscreen", "pip"].includes(requested)) mode = requested;
    applyStage();
    reply(event.source, msg.id, { mode });
    return;
  }
  if (msg.method === "ui/message" || msg.method === "ui/update-model-context") {
    reply(event.source, msg.id, {});
    return;
  }
  if (msg.method === "ui/open-link" || msg.method === "ui/download-file") {
    reply(event.source, msg.id, { isError: false });
    return;
  }
  if (msg.method === "tools/call") {
    reply(event.source, msg.id, {
      content: [{ type: "text", text: JSON.stringify({ view: "map" }) }],
      structuredContent: { ...FLEET_SNAPSHOT, view: "map" },
    });
    return;
  }
  if (msg.id != null) reply(event.source, msg.id, {});
});

preset.addEventListener("change", applyStage);
themeSel.addEventListener("change", () => {
  theme = themeSel.value as "light" | "dark";
  applyStage();
});
document.getElementById("mode-inline")?.addEventListener("click", () => {
  mode = "inline";
  applyStage();
});
document.getElementById("mode-full")?.addEventListener("click", () => {
  mode = "fullscreen";
  applyStage();
});
document.getElementById("mode-pip")?.addEventListener("click", () => {
  mode = "pip";
  applyStage();
});
window.addEventListener("resize", () => {
  if (mode !== "inline" || preset.value === "100%") applyStage();
});

iframe.src = "/mcp-app.html";
requestAnimationFrame(applyStage);
