import { StreamEvent } from "../../services/api";

export function Timeline({ events }: { events: StreamEvent[] }) {
  const stageEvents = events.filter((e) => e.event === "stage_start" || e.event === "stage_complete");
  const selection = events.find((e) => e.event === "selection");

  return (
    <div style={{ marginTop: "1rem" }}>
      <h3>Pipeline Timeline</h3>
      {selection && (
        <div
          className="timeline-item"
          style={{
            padding: "0.5rem",
            marginBottom: "0.5rem",
            background: selection.needs_confirmation ? "#fef3c7" : "#ecfdf5",
            borderRadius: "0.5rem",
          }}
        >
          <strong>Selected metric:</strong> {String(selection.metric_id)}
          {selection.confidence != null && (
            <span> (confidence: {Number(selection.confidence).toFixed(2)})</span>
          )}
          {selection.needs_confirmation === true && (
            <div style={{ color: "#92400e" }}>
              Low confidence — confirm metric selection below to continue.
            </div>
          )}
          {Array.isArray(selection.dimensions) && selection.dimensions.length > 0 && (
            <div style={{ marginTop: "0.25rem" }}>
              <strong>Breakdown:</strong> {(selection.dimensions as string[]).join(", ")}
            </div>
          )}
          {Array.isArray(selection.dimension_warnings) && selection.dimension_warnings.length > 0 && (
            <div style={{ color: "#92400e", marginTop: "0.25rem" }}>
              {(selection.dimension_warnings as string[]).join(" ")}
            </div>
          )}
          {selection.rationale != null && String(selection.rationale) && (
            <div style={{ marginTop: "0.25rem" }}>{String(selection.rationale)}</div>
          )}
        </div>
      )}
      {stageEvents.map((e, i) => (
        <div key={i} className="timeline-item">
          {String(e.event)} — {String(e.stage)}
          {e.elapsed_sec != null ? ` (${e.elapsed_sec}s)` : ""}
        </div>
      ))}
    </div>
  );
}
