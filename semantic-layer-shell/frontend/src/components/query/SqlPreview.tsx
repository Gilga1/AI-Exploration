import { StreamEvent } from "../../services/api";

export function SqlPreview({ events }: { events: StreamEvent[] }) {
  const preview = [...events].reverse().find((e) => e.event === "sql_preview");
  if (!preview) return null;

  return (
    <div style={{ marginTop: "1rem" }}>
      <h3>SQL Preview</h3>
      <p>
        <strong>Metric:</strong> {String(preview.metric_id)} | <strong>Version:</strong>{" "}
        {String(preview.graph_version_id)}
      </p>
      <pre className="sql">{String(preview.sql)}</pre>
    </div>
  );
}
