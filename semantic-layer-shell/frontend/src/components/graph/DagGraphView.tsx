import { useMemo } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

type DagPayload = {
  nodes: Array<{ id: string; label: string; name: string }>;
  edges: Array<{ source: string; target: string; type: string }>;
};

const LABEL_COLORS: Record<string, string> = {
  DataSource: "#dbeafe",
  Measure: "#dcfce7",
  Metric: "#fef3c7",
  Entity: "#fae8ff",
};

export function DagGraphView({ dag, onSelect }: { dag: DagPayload; onSelect: (id: string) => void }) {
  const nodes: Node[] = useMemo(
    () =>
      dag.nodes.map((n, i) => ({
        id: n.id,
        position: { x: (i % 4) * 220, y: Math.floor(i / 4) * 120 },
        data: { label: `${n.name}\n(${n.label})` },
        style: {
          background: LABEL_COLORS[n.label] || "#fff",
          border: "1px solid #94a3b8",
          borderRadius: 8,
          padding: 8,
          fontSize: 12,
          whiteSpace: "pre-wrap",
          width: 180,
        },
      })),
    [dag.nodes],
  );

  const edges: Edge[] = useMemo(
    () =>
      dag.edges.map((e, i) => ({
        id: `e-${i}`,
        source: e.source,
        target: e.target,
        label: e.type,
        animated: e.type === "JOINS_TO",
      })),
    [dag.edges],
  );

  return (
    <div style={{ height: 420, border: "1px solid #e2e8f0", borderRadius: 8 }}>
      <ReactFlow nodes={nodes} edges={edges} onNodeClick={(_, node) => onSelect(node.id)} fitView>
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}
