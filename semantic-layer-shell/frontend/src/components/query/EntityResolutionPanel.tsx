import { StreamEvent } from "../../services/api";

type Resolution = {
  mention_text?: string;
  entity_type?: string;
  status?: string;
  key_value?: string;
  label_value?: string;
  resolution_method?: string;
};

export function EntityResolutionPanel({ events }: { events: StreamEvent[] }) {
  const resolutionEvent = events.find((e) => e.event === "entity_resolution");
  const timeEvent = events.find((e) => e.event === "time_resolution");
  if (!resolutionEvent && !timeEvent) return null;

  const resolutions = (resolutionEvent?.resolutions as Resolution[]) || [];

  return (
    <div
      style={{
        marginTop: "1rem",
        padding: "0.75rem",
        background: "#f8fafc",
        borderRadius: "0.5rem",
        border: "1px solid #e2e8f0",
      }}
    >
      <h3>Resolved filters</h3>
      {resolutions.length === 0 && <p>No entity mentions resolved.</p>}
      <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
        {resolutions.map((r, idx) => (
          <li key={`${r.entity_type}-${idx}`}>
            <strong>{r.entity_type}</strong>: {r.label_value || r.mention_text}
            {r.key_value != null && (
              <>
                {" "}
                → <code>{String(r.key_value)}</code>
              </>
            )}
            {r.status && r.status !== "resolved" && (
              <span style={{ color: "#b45309" }}> ({r.status})</span>
            )}
          </li>
        ))}
      </ul>
      {timeEvent?.time && (
        <p style={{ marginTop: "0.75rem", marginBottom: 0 }}>
          Time range: <code>{JSON.stringify(timeEvent.time)}</code>
        </p>
      )}
    </div>
  );
}
