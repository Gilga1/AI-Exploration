import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Activity } from "lucide-react";

import { apiRequest, TraceSummary } from "../api/client";

export default function Traces() {
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [error, setError] = useState<string>();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    apiRequest<TraceSummary[]>("/api/v1/traces")
      .then((data) => setTraces(data))
      .catch((requestError) =>
        setError(requestError instanceof Error ? requestError.message : "Failed to load traces"),
      )
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading) return <p className="text-sm text-slate-500">Loading traces…</p>;
  if (error)
    return <p className="rounded-md bg-rose-400/10 p-3 text-sm text-rose-200">{error}</p>;

  return (
    <section className="w-full max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Traces</h1>
        <p className="mt-1 text-sm text-slate-400">
          OTel spans captured from the RAG chain. Run an evaluation to generate new traces.
        </p>
      </div>

      {traces.length === 0 && (
        <p className="rounded-md border border-slate-800 bg-slate-900/70 p-4 text-sm text-slate-400">
          No traces yet — trigger <span className="text-slate-200">Run evaluation</span> on the
          Evaluations page first.
        </p>
      )}

      {traces.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-slate-800 bg-slate-900/70">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-950/50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-5 py-3 font-medium">Trace</th>
                <th className="px-5 py-3 font-medium">Started</th>
                <th className="px-5 py-3 font-medium">Duration</th>
                <th className="px-5 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 text-slate-300">
              {traces.map((trace) => (
                <tr key={trace.id} className="transition hover:bg-slate-800/40">
                  <td className="px-5 py-3">
                    <Link
                      to={`/traces/${trace.id}`}
                      className="flex items-center gap-2 font-medium text-cyan-300 hover:text-cyan-200"
                    >
                      <Activity className="h-4 w-4" />
                      {trace.name}
                    </Link>
                  </td>
                  <td className="px-5 py-3 text-slate-400">
                    {trace.start_time ? new Date(trace.start_time).toLocaleString() : "—"}
                  </td>
                  <td className="px-5 py-3 tabular-nums">
                    {trace.duration_ms != null ? `${trace.duration_ms.toFixed(1)} ms` : "—"}
                  </td>
                  <td className="px-5 py-3">
                    <span
                      className={`rounded-full px-2 py-1 text-xs font-medium ${
                        trace.status === "ERROR"
                          ? "bg-rose-400/10 text-rose-300"
                          : "bg-emerald-400/10 text-emerald-300"
                      }`}
                    >
                      {trace.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
