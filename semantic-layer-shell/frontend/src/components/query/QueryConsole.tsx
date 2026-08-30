import { useState } from "react";
import { useSemanticQuery } from "../../hooks/useSemanticQuery";
import { Timeline } from "./Timeline";
import { SqlPreview } from "./SqlPreview";
import { ResultsPanel } from "./ResultsPanel";

export function QueryConsole() {
  const { events, loading, error, runQuery } = useSemanticQuery();
  const [question, setQuestion] = useState("What is the net flow ratio by fund?");

  return (
    <div className="panel">
      <h2>Query Console</h2>
      <textarea rows={3} value={question} onChange={(e) => setQuestion(e.target.value)} />
      <div style={{ marginTop: "0.75rem" }}>
        <button className="primary" disabled={loading} onClick={() => runQuery(question)}>
          {loading ? "Running..." : "Ask"}
        </button>
      </div>
      {error && <p style={{ color: "#b91c1c" }}>{error}</p>}
      <Timeline events={events} />
      <SqlPreview events={events} />
      <ResultsPanel events={events} />
    </div>
  );
}
