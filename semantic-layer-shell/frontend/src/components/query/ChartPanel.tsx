import { VegaLite } from "react-vega";
import { StreamEvent } from "../../services/api";

type ChartPayload = {
  charts?: Array<{
    id: string;
    title?: string;
    template_id?: string;
    library?: string;
    spec?: Record<string, unknown>;
  }>;
  recommended_chart_id?: string;
};

export function ChartPanel({ events }: { events: StreamEvent[] }) {
  const viz = [...events].reverse().find((e) => e.event === "visualization");
  if (!viz?.chart) return null;

  const chartPayload = viz.chart as ChartPayload;
  const charts = chartPayload.charts || [];
  const primary = charts.find((c) => c.id === chartPayload.recommended_chart_id) || charts[0];
  if (!primary?.spec) return null;

  return (
    <div style={{ marginTop: "1rem" }}>
      <h3>Chart</h3>
      <p style={{ margin: "0.25rem 0", color: "#475569" }}>
        {primary.title || primary.template_id || "Visualization"}
      </p>
      <ChartSpec spec={primary.spec} />
    </div>
  );
}

function ChartSpec({ spec }: { spec: Record<string, unknown> }) {
  return (
    <div style={{ maxWidth: "100%", overflowX: "auto" }}>
      <VegaLite spec={spec} actions={false} />
    </div>
  );
}
