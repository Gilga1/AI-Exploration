import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest, RagMetrics } from "../../api/client";

const scoreColor = (score: number | null) => {
  if (score == null) return "bg-slate-700";
  if (score >= 0.7) return "bg-emerald-400";
  if (score >= 0.5) return "bg-amber-400";
  return "bg-rose-400";
};

interface MetricsOverviewProps {
  metrics?: RagMetrics;
  error?: string;
  loading?: boolean;
}

export function MetricsOverview({ metrics, error, loading }: MetricsOverviewProps) {
  if (error) {
    return (
      <p className="rounded-md bg-rose-400/10 p-3 text-sm text-rose-200">
        {error}
      </p>
    );
  }
  if (loading || !metrics) {
    return <p className="text-sm text-slate-500">Loading metrics…</p>;
  }

  return (
    <div className="space-y-4">
      {metrics.alerts && metrics.alerts.length > 0 ? (
        <div className="space-y-2 rounded-lg border border-rose-500/40 bg-rose-500/10 p-4">
          <div className="text-sm font-medium text-rose-100">Active alerts</div>
          {metrics.alerts.map((alert) => (
            <p key={alert.metric} className="text-sm text-rose-100/90">
              {alert.metric} averaged {alert.avg_score.toFixed(2)} over{" "}
              {alert.cases_scored} traces (threshold {alert.threshold.toFixed(2)}
              {alert.window_hours ? `, last ${alert.window_hours}h` : ""})
            </p>
          ))}
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {metrics.summary.map((metric) => (
          <div
            key={metric.name}
            className="rounded-lg border border-slate-800 bg-slate-900/70 p-4"
          >
            <div className="text-xs uppercase tracking-wide text-slate-500">
              {metric.name}
            </div>
            <div className="mt-2 text-2xl font-semibold tabular-nums text-white">
              {metric.avg_score != null ? metric.avg_score.toFixed(2) : "—"}
            </div>
            <div className="mt-3 h-1.5 w-full rounded bg-slate-950/70">
              <div
                className={`h-1.5 rounded ${scoreColor(metric.avg_score)}`}
                style={{ width: `${(metric.avg_score ?? 0) * 100}%` }}
              />
            </div>
            <div className="mt-2 text-xs text-slate-500">
              {metric.cases_scored} trace{metric.cases_scored === 1 ? "" : "s"}{" "}
              scored
            </div>
          </div>
        ))}
      </div>
      <p className="text-xs text-slate-500">
        {metrics.total_traces_scored} traces evaluated asynchronously ·{" "}
        <Link to="/evaluations" className="text-cyan-300 hover:text-cyan-200">
          run the golden dataset
        </Link>{" "}
        to generate more
      </p>
    </div>
  );
}

interface RagMetricsPanelProps {
  metrics?: RagMetrics;
  panelError?: string;
}

export function RagMetricsPanel({ metrics, panelError }: RagMetricsPanelProps) {
  if (panelError) {
    return (
      <p className="rounded-md bg-rose-400/10 p-3 text-sm text-rose-200">
        {panelError}
      </p>
    );
  }
  if (!metrics?.per_trace?.length) return null;

  return (
    <div className="overflow-hidden rounded-lg border border-slate-800 bg-slate-900/70">
      <div className="border-b border-slate-800 px-5 py-3 text-sm font-medium text-slate-200">
        Recent scored traces
      </div>
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-950/50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-5 py-2 font-medium">Trace</th>
            <th className="px-5 py-2 font-medium">Metric</th>
            <th className="px-5 py-2 font-medium">Score</th>
            <th className="px-5 py-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800 text-slate-300">
          {metrics.per_trace.slice(-12).map((row, index) => (
            <tr key={`${row.trace_id}-${row.metric}-${index}`}>
              <td className="max-w-[180px] truncate px-5 py-2">
                <Link
                  to={`/traces/${row.trace_id}`}
                  className="font-mono text-xs text-cyan-300 hover:text-cyan-200"
                  title={row.trace_id}
                >
                  {row.trace_id.slice(0, 12)}…
                </Link>
              </td>
              <td className="px-5 py-2">{row.metric}</td>
              <td className="tabular-nums px-5 py-2">
                {row.score != null ? row.score.toFixed(2) : "—"}
              </td>
              <td className="px-5 py-2">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ${
                    row.status === "passed"
                      ? "bg-emerald-400/10 text-emerald-300"
                      : row.status === "failed"
                        ? "bg-rose-400/10 text-rose-300"
                        : row.status === "partial"
                          ? "bg-amber-400/10 text-amber-300"
                          : "bg-slate-700 text-slate-300"
                  }`}
                >
                  {row.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function useRagMetrics() {
  const [metrics, setMetrics] = useState<RagMetrics>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    apiRequest<RagMetrics>("/api/v1/metrics/rag?per_trace=true")
      .then(setMetrics)
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to load metrics"),
      );
  }, []);

  return { metrics, error, loading: !metrics && !error };
}
