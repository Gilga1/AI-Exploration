import { StreamEvent } from "../../services/api";

type StructuredInsight = {
  id?: string;
  text?: string;
  confidence?: string;
};

export function InsightsPanel({ events }: { events: StreamEvent[] }) {
  const insights = events.find((e) => e.event === "insights");
  const analysis = events.find((e) => e.event === "analysis");
  const explorer = events.find((e) => e.event === "explorer");
  const cacheHit = events.find((e) => e.event === "cache_hit");

  const headline = insights ? String(insights.headline || insights.delta || "") : "";
  const bullets = (insights?.insights as StructuredInsight[]) || [];
  const followUps = (insights?.follow_ups as string[]) || [];

  return (
    <div style={{ marginTop: "1rem" }}>
      {cacheHit && <p className="timeline-item">Cache hit — identical graph resolution reused.</p>}
      {insights && (
        <div>
          <h3>Insights</h3>
          {headline && <p style={{ fontWeight: 600 }}>{headline}</p>}
          {bullets.length > 0 && (
            <ul>
              {bullets.map((item) => (
                <li key={item.id || item.text}>
                  {item.text}
                  {item.confidence && (
                    <span
                      style={{
                        marginLeft: "0.5rem",
                        fontSize: "0.75rem",
                        padding: "0.1rem 0.4rem",
                        borderRadius: "0.25rem",
                        background: "#e2e8f0",
                      }}
                    >
                      {item.confidence}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
          {followUps.length > 0 && (
            <div style={{ marginTop: "0.5rem" }}>
              <strong>Follow-ups</strong>
              <ul>
                {followUps.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          )}
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
