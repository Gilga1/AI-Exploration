import { useEffect, useState } from "react";

import { apiRequest, AgentMetrics } from "../../api/client";

export function AgentLoopChart() {
  const [metrics, setMetrics] = useState<AgentMetrics>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    apiRequest<AgentMetrics>("/api/v1/metrics/agent")
      .then(setMetrics)
      .catch((e) =>
        setError(
          e instanceof Error ? e.message : "Failed to load agent metrics",
        ),
      );
  }, []);

  if (error)
    return (
      <p className="rounded-md bg-rose-400/10 p-3 text-sm text-rose-200">
        {error}
      </p>
    );
  if (!metrics) return null;

  const efficient = metrics.runs.filter(
    (r) => r.classification === "efficient",
  ).length;
  const thrashing = metrics.runs.filter(
    (r) => r.classification === "thrashing",
  ).length;
  const classified = efficient + thrashing || 1;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
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
            <div className="mt-2 text-xs text-slate-500">
              {metric.cases_scored} agent run
              {metric.cases_scored === 1 ? "" : "s"} scored
            </div>
          </div>
        ))}
      </div>

      {metrics.runs.length > 0 && (
        <>
          {/* Efficient vs thrashing split */}
          <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-4">
            <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
              <span>Run classification</span>
              <span>
                <span className="text-emerald-300">{efficient} efficient</span>
                {" · "}
                <span className="text-rose-300">{thrashing} thrashing</span>
              </span>
            </div>
            <div className="flex h-3 w-full overflow-hidden rounded bg-slate-950/70">
              <div
                className="h-3 bg-emerald-400"
                style={{ width: `${(efficient / classified) * 100}%` }}
              />
              <div
                className="h-3 bg-rose-400"
                style={{ width: `${(thrashing / classified) * 100}%` }}
              />
            </div>
          </div>

          {/* Per-run table */}
          <div className="overflow-hidden rounded-lg border border-slate-800 bg-slate-900/70">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-950/50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-2 font-medium">Agent run</th>
                  <th className="px-5 py-2 font-medium">Tool accuracy</th>
                  <th className="px-5 py-2 font-medium">Task success</th>
                  <th className="px-5 py-2 font-medium">Loop efficiency</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 text-slate-300">
                {metrics.runs.slice(-10).map((run) => (
                  <tr key={run.trace_id}>
                    <td className="px-5 py-2 font-mono text-xs text-cyan-300">
                      {run.trace_id.slice(0, 12)}…
                    </td>
                    <td className="tabular-nums px-5 py-2">
                      {run.tool_correctness != null
                        ? run.tool_correctness.toFixed(2)
                        : "—"}
                    </td>
                    <td className="px-5 py-2">
                      {run.task_success ? (
                        <span className="rounded-full bg-emerald-400/10 px-2 py-0.5 text-xs text-emerald-300">
                          success
                        </span>
                      ) : (
                        <span className="rounded-full bg-rose-400/10 px-2 py-0.5 text-xs text-rose-300">
                          failed
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${
                          run.classification === "efficient"
                            ? "bg-emerald-400/10 text-emerald-300"
                            : run.classification === "thrashing"
                              ? "bg-rose-400/10 text-rose-300"
                              : "bg-slate-700 text-slate-300"
                        }`}
                      >
                        {run.classification}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
