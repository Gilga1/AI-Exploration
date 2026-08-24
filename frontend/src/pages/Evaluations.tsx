import { useState } from "react";

import { EvaluationScorecard, runEvaluation } from "../api/client";

const statusStyles = {
  completed: "bg-emerald-400/10 text-emerald-300",
  passed: "bg-emerald-400/10 text-emerald-300",
  partial: "bg-amber-400/10 text-amber-300",
  failed: "bg-rose-400/10 text-rose-300",
  skipped: "bg-slate-700 text-slate-300",
};

export default function Evaluations() {
  const [scorecard, setScorecard] = useState<EvaluationScorecard>();
  const [error, setError] = useState<string>();
  const [isRunning, setIsRunning] = useState(false);

  async function handleRun() {
    setIsRunning(true);
    setError(undefined);
    try {
      setScorecard(await runEvaluation());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Evaluation failed");
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <section className="w-full max-w-4xl space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-white">Evaluations</h1>
          <p className="mt-1 text-sm text-slate-400">
            Run the Phase 1 golden dataset against the offline RAG chain.
          </p>
        </div>
        <button
          className="rounded-md bg-cyan-400 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isRunning}
          onClick={handleRun}
          type="button"
        >
          {isRunning ? "Running…" : "Run evaluation"}
        </button>
      </div>

      {error && <p className="rounded-md bg-rose-400/10 p-3 text-sm text-rose-200">{error}</p>}

      {scorecard && (
        <div className="overflow-hidden rounded-lg border border-slate-800 bg-slate-900/70">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 px-5 py-4 text-sm">
            <span className="text-slate-300">
              {scorecard.dataset} · {scorecard.total_cases} cases · {scorecard.llm_provider}
            </span>
            <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusStyles[scorecard.status]}`}>
              {scorecard.status}
            </span>
          </div>
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-950/50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-5 py-3 font-medium">Metric</th>
                <th className="px-5 py-3 font-medium">Score</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 text-slate-300">
              {scorecard.metrics.map((metric) => (
                <tr key={metric.name}>
                  <td className="px-5 py-4 font-medium text-white">{metric.name}</td>
                  <td className="px-5 py-4">
                    {metric.score === null ? "—" : metric.score.toFixed(2)}
                  </td>
                  <td className="px-5 py-4">
                    <span className={`rounded-full px-2 py-1 text-xs font-medium ${statusStyles[metric.status]}`}>
                      {metric.status}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-slate-400">
                    {metric.reason ?? (metric.cases_scored ? `${metric.cases_scored} cases scored` : "")}
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
