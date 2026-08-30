import { StreamEvent } from "../../services/api";

export function InsightsPanel({ events }: { events: StreamEvent[] }) {
  const insights = events.find((e) => e.event === "insights");
  const analysis = events.find((e) => e.event === "analysis");
  const explorer = events.find((e) => e.event === "explorer");
  const cacheHit = events.find((e) => e.event === "cache_hit");

  return (
    <div style={{ marginTop: "1rem" }}>
      {cacheHit && <p className="timeline-item">Cache hit — identical graph resolution reused.</p>}
      {insights && (
        <div>
          <h3>Insights</h3>
          <p>{String(insights.delta)}</p>
        </div>
      )}
      {analysis && (
        <details style={{ marginTop: "0.5rem" }}>
          <summary>Statistical analysis</summary>
          <pre style={{ fontSize: "0.8rem" }}>{JSON.stringify(analysis.analysis, null, 2)}</pre>
        </details>
      )}
      {explorer && Array.isArray(explorer.related_metrics) && (
        <div style={{ marginTop: "0.5rem" }}>
          <h3>Related metrics</h3>
          <ul>
            {(explorer.related_metrics as Array<{ id: string; name: string }>).map((m) => (
              <li key={m.id}>
                {m.name} <small>({m.id})</small>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
