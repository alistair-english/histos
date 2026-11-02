import {
  Handle,
  Position,
  ReactFlow,
  type NodeProps,
} from "@xyflow/react";
import { useEffect, useMemo, useState } from "react";
import {
  layoutGraph,
  type Entry,
  type EntryNode,
  type GraphSnapshot,
} from "./graph.ts";

async function loadGraph(): Promise<GraphSnapshot> {
  const response = await fetch("/api/graph");
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return (await response.json()) as GraphSnapshot;
}

function EntryNodeView({ data, selected }: NodeProps<EntryNode>) {
  const { entry, text } = data;
  const className = [
    "entry-node",
    `entry-node--${entry.kind}`,
    `entry-node--${entry.author}`,
    selected ? "entry-node--selected" : "",
  ].join(" ");

  return (
    <article className={className}>
      <Handle type="target" position={Position.Top} />
      <div>{text}</div>
      <Handle type="source" position={Position.Bottom} />
    </article>
  );
}

const nodeTypes = { entry: EntryNodeView };

export function App() {
  const [graph, setGraph] = useState<GraphSnapshot>({ entries: [], edges: [] });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadGraph().then(setGraph, (caught: unknown) => {
      setError(caught instanceof Error ? caught.message : String(caught));
    });
  }, []);

  const elements = useMemo(() => {
    const laidOut = layoutGraph(graph);
    return {
      ...laidOut,
      nodes: laidOut.nodes.map((node) => ({ ...node, selected: node.id === selectedId })),
    };
  }, [graph, selectedId]);
  const selectedEntry: Entry | undefined = graph.entries.find((entry) => entry.id === selectedId);

  return (
    <main className="workspace">
      <section className="graph" aria-label="Conversation graph">
        <ReactFlow
          fitView
          edges={elements.edges}
          nodes={elements.nodes}
          nodesDraggable={false}
          nodesConnectable={false}
          nodeTypes={nodeTypes}
          onNodeClick={(_event, node) => setSelectedId(node.id)}
          proOptions={{ hideAttribution: true }}
        />
      </section>
      <aside className="details">
        {selectedEntry === undefined ? (
          <p>Select a node to read its full content.</p>
        ) : (
          <article>
            <small>
              {selectedEntry.author} · {selectedEntry.kind}
            </small>
            <p>{selectedEntry.content}</p>
          </article>
        )}
        {error !== null && <p role="alert">{error}</p>}
      </aside>
    </main>
  );
}
