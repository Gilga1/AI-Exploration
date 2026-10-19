export type ViewId = "overview" | "map" | "dashboard" | "motion" | "modals" | "interact";

export const VIEWS: { id: ViewId; label: string }[] = [
  { id: "overview", label: "Home" },
  { id: "map", label: "Live map" },
  { id: "dashboard", label: "Ops board" },
  { id: "motion", label: "Briefing" },
  { id: "modals", label: "Sheets" },
  { id: "interact", label: "Filters" },
];

export function $(id: string): HTMLElement {
  const el = document.getElementById(id);
  if (!el) throw new Error(`Missing #${id}`);
  return el;
}

export function formatDelta(pct: number): string {
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

export function applySafeArea(root: HTMLElement, insets?: {
  top: number;
  right: number;
  bottom: number;
  left: number;
}) {
  const pad = insets ?? { top: 8, right: 8, bottom: 12, left: 8 };
  root.style.paddingTop = `${pad.top}px`;
  root.style.paddingRight = `${pad.right}px`;
  root.style.paddingBottom = `${pad.bottom}px`;
  root.style.paddingLeft = `${pad.left}px`;
}

export function applyHostVariables(vars?: Record<string, string | undefined>) {
  const root = document.documentElement;
  if (!vars) return;
  for (const [key, value] of Object.entries(vars)) {
    if (value) root.style.setProperty(key, value);
  }
}

export function sparkPath(values: number[], w: number, h: number): string {
  if (!values.length) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * w;
      const y = h - ((v - min) / span) * h;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}
