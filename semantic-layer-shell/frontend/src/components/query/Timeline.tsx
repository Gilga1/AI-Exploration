import { StreamEvent } from "../../services/api";

export function Timeline({ events }: { events: StreamEvent[] }) {
  const stageEvents = events.filter((e) => e.event === "stage_start" || e.event === "stage_complete");
  if (!stageEvents.length) return null;

  return (
    <div style={{ marginTop: "1rem" }}>
      <h3>Pipeline Timeline</h3>
      {stageEvents.map((e, i) => (
        <div key={i} className="timeline-item">
          {String(e.event)} — {String(e.stage)}
          {e.elapsed_sec != null ? ` (${e.elapsed_sec}s)` : ""}
        </div>
      ))}
    </div>
  );
}
