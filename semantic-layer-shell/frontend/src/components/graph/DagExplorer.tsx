import { useEffect, useState } from "react";
import { fetchJson } from "../../services/api";
import { DagGraphView } from "./DagGraphView";
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
      {dag && dag.nodes.length > 0 ? (
        <DagGraphView key={subgraph} dag={dag} onSelect={setSelectedId} />
      ) : (
        <p>No nodes in this subgraph.</p>
      )}
      <div style={{ marginTop: "1rem" }}>
        <NodeInspector nodeId={selectedId} />
      </div>
    </div>
  );
}
