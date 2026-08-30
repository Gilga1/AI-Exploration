import { useState } from "react";
import { useSemanticQuery } from "../../hooks/useSemanticQuery";
import { Timeline } from "./Timeline";
import { SqlPreview } from "./SqlPreview";
import { ResultsPanel } from "./ResultsPanel";
import { InsightsPanel } from "./InsightsPanel";
import { StreamEvent } from "../../services/api";

function ConfirmationPanel({
  event,
  onConfirm,
  loading,
}: {
  event: StreamEvent;
  onConfirm: (metricId: string) => void;
  loading: boolean;
}) {
  const candidates = (event.candidates as StreamEvent[]) || [];
  const suggested = String(event.metric_id || "");

  return (
    <div
      style={{
        marginTop: "1rem",
        padding: "0.75rem",
        background: "#fef3c7",
        borderRadius: "0.5rem",
        border: "1px solid #f59e0b",
      }}
    >
      <strong>Confirm metric selection</strong>
      <p style={{ margin: "0.5rem 0" }}>{String(event.message || "")}</p>
      <p>
        Suggested: <code>{suggested}</code>
        {event.confidence != null && ` (confidence: ${Number(event.confidence).toFixed(2)})`}
      </p>
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.5rem" }}>
        <button className="primary" disabled={loading} onClick={() => onConfirm(suggested)}>
          Continue with {suggested}
        </button>
        {candidates
          .filter((c) => String(c.id) !== suggested)
          .slice(0, 4)
          .map((c) => (
            <button key={String(c.id)} disabled={loading} onClick={() => onConfirm(String(c.id))}>
              Use {String(c.id)}
            </button>
          ))}
      </div>
    </div>
  );
}

export function QueryConsole() {
  const { events, loading, error, runQuery } = useSemanticQuery();
  const [question, setQuestion] = useState("What is the net flow ratio by fund?");
  const [revisionHint, setRevisionHint] = useState("");

  const confirmationEvent = events.find((e) => e.event === "confirmation_required");

  return (
    <div className="panel">
      <h2>Query Console</h2>
      <textarea rows={3} value={question} onChange={(e) => setQuestion(e.target.value)} />
      <input
        style={{ marginTop: "0.5rem" }}
        placeholder="Revision hint (optional) — e.g. use gross basis instead"
        value={revisionHint}
        onChange={(e) => setRevisionHint(e.target.value)}
      />
      <div style={{ marginTop: "0.75rem" }}>
        <button
          className="primary"
          disabled={loading}
          onClick={() => runQuery(question, undefined, revisionHint || undefined)}
        >
          {loading ? "Running..." : "Ask"}
        </button>
      </div>
      {error && <p style={{ color: "#b91c1c" }}>{error}</p>}
      {confirmationEvent && (
        <ConfirmationPanel
          event={confirmationEvent}
          loading={loading}
          onConfirm={(metricId) => runQuery(question, metricId, revisionHint || undefined)}
        />
      )}
      <Timeline events={events} />
      <SqlPreview events={events} />
      <ResultsPanel events={events} />
      <InsightsPanel events={events} />
    </div>
  );
}
