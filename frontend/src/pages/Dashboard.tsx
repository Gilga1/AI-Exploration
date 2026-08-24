import { AgentLoopChart } from "../components/dashboard/AgentLoopChart";
import { MetricsOverview, RagMetricsPanel } from "../components/dashboard/MetricsOverview";

export default function Dashboard() {
  return (
    <section className="w-full max-w-4xl space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-white">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-400">
          RAG and agent metrics computed asynchronously from captured traces.
        </p>
      </div>

      <div className="space-y-4">
        <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500">RAG metrics</h2>
        <MetricsOverview />
        <RagMetricsPanel />
      </div>

      <div className="space-y-4">
        <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500">Agent loop</h2>
        <AgentLoopChart />
      </div>
    </section>
  );
}
