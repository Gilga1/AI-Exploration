import { useState } from "react";
import { useSemanticQuery } from "../../hooks/useSemanticQuery";
import { Timeline } from "./Timeline";
import { SqlPreview } from "./SqlPreview";
import { ResultsPanel } from "./ResultsPanel";
import { InsightsPanel } from "./InsightsPanel";

export function QueryConsole() {
  const { events, loading, error, runQuery } = useSemanticQuery();
  const [question, setQuestion] = useState("What is the net flow ratio by fund?");
  const [revisionHint, setRevisionHint] = useState("");

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
      <Timeline events={events} />
      <SqlPreview events={events} />
      <ResultsPanel events={events} />
      <InsightsPanel events={events} />
    </div>
  );
}
