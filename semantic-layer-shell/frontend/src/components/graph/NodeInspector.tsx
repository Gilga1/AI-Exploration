import { useEffect, useState } from "react";
import { fetchJson } from "../../services/api";

export function NodeInspector({ nodeId }: { nodeId: string | null }) {
  const [node, setNode] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (!nodeId) {
      setNode(null);
      return;
    }
    fetchJson<Record<string, unknown>>(`/api/v1/graph/nodes/${nodeId}`)
      .then(setNode)
      .catch(() => setNode(null));
  }, [nodeId]);

  if (!nodeId) return <div>Select a node to inspect.</div>;
  if (!node) return <div>Loading {nodeId}...</div>;

  return (
    <div>
      <h3>Node Inspector</h3>
      <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(node, null, 2)}</pre>
    </div>
  );
}
