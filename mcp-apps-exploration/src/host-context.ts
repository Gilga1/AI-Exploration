/**
 * HostContext shape copied from the MCP Apps spec types
 * (modelcontextprotocol/ext-apps `src/spec.types.ts`).
 *
 * This is the evidence that iframe size is host-controlled, not a
 * protocol-fixed chat-column width.
 */
export type DisplayMode = "inline" | "fullscreen" | "pip";

export type ContainerDimensions = (
  | { height: number }
  | { maxHeight?: number }
) & (
  | { width: number }
  | { maxWidth?: number }
);

export interface HostContext {
  theme?: "light" | "dark";
  displayMode?: DisplayMode;
  availableDisplayModes?: DisplayMode[];
  containerDimensions?: ContainerDimensions;
  locale?: string;
  timeZone?: string;
  platform?: "web" | "desktop" | "mobile";
  deviceCapabilities?: { touch?: boolean; hover?: boolean };
  safeAreaInsets?: { top: number; right: number; bottom: number; left: number };
  styles?: { variables?: Record<string, string | undefined> };
}

export const SPEC_NOTES = {
  protocolVersion: "2026-01-26",
  displayModes: ["inline", "fullscreen", "pip"] as const,
  claudeDesktopObservedInline: {
    width: 736,
    maxHeight: 5000,
    availableDisplayModes: ["inline", "fullscreen"] as const,
    source: "https://github.com/modelcontextprotocol/ext-apps/issues/688",
  },
  specInitializeExampleWidth: 400,
  specInitializeExampleMaxHeight: 600,
  specSource:
    "https://github.com/modelcontextprotocol/ext-apps/blob/main/src/spec.types.ts",
};

export function describeDimensions(dims?: ContainerDimensions): string {
  if (!dims) return "unknown (host has not sent containerDimensions yet)";
  const width =
    "width" in dims && typeof dims.width === "number"
      ? `fixed width ${dims.width}px`
      : "maxWidth" in dims && dims.maxWidth != null
        ? `flexible up to ${dims.maxWidth}px`
        : "width not specified";
  const height =
    "height" in dims && typeof dims.height === "number"
      ? `fixed height ${dims.height}px`
      : "maxHeight" in dims && dims.maxHeight != null
        ? `content-driven up to ${dims.maxHeight}px`
        : "height not specified";
  return `${width}; ${height}`;
}
