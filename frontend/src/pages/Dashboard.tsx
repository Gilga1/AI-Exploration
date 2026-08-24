import { MetricsOverview, RagMetricsPanel } from "../components/dashboard/MetricsOverview";

export default function Dashboard() {
  return (
    <section className="w-full max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-400">
          RAG judge scores computed asynchronously from captured traces.
        </p>
      </div>
      <MetricsOverview />
      <RagMetricsPanel />
    </section>
  );
}
