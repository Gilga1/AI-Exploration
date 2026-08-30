import { useEffect, useState } from "react";
import { fetchJson } from "../../services/api";
import { NodeInspector } from "./NodeInspector";

type DagPayload = {
  nodes: Array<{ id: string; label: string; name: string }>;
  edges: Array<{ source: string; target: string; type: string }>;
  subgraph: string;
};

export function DagExplorer() {
  const [subgraph, setSubgraph] = useState("composition");
  const [dag, setDag] = useState<DagPayload | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<DagPayload>(`/api/v1/graph/dag?subgraph=${subgraph}`)
      .then(setDag)
      .catch(() => setDag({ nodes: [], edges: [], subgraph }));
  }, [subgraph]);

  return (
    <div className="panel">
      <h2>DAG Explorer</h2>
      <div className="dag-layers">
        {["lineage", "join", "composition"].map((layer) => (
          <button key={layer} className={subgraph === layer ? "active" : ""} onClick={() => setSubgraph(layer)}>
            {layer}
          </button>
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
        <div>
          <h3>Nodes ({dag?.nodes.length ?? 0})</h3>
          <ul>
            {dag?.nodes.map((n) => (
              <li key={n.id}>
                <button onClick={() => setSelectedId(n.id)}>
                  {n.name} <small>({n.label})</small>
                </button>
              </li>
            ))}
          </ul>
          <h3>Edges ({dag?.edges.length ?? 0})</h3>
          <ul>
            {dag?.edges.map((e, i) => (
              <li key={i}>
                {e.source} —{e.type}→ {e.target}
              </li>
            ))}
          </ul>
        </div>
        <NodeInspector nodeId={selectedId} />
      </div>
    </div>
  );
}
