import dagre from "@dagrejs/dagre";
import type { Edge, Node } from "@xyflow/react";

export type Author = "user" | "agent";
export type EntryKind = "question" | "message" | "concept" | "tool_call";

export interface Entry {
  id: string;
  author: Author;
  kind: EntryKind;
  content: string;
  label: string | null;
}

export interface ParentEdge {
  parent_id: string;
  child_id: string;
}

export interface GraphSnapshot {
  entries: Entry[];
  edges: ParentEdge[];
}

export interface EntryNodeData extends Record<string, unknown> {
  entry: Entry;
  text: string;
}

export type EntryNode = Node<EntryNodeData, "entry">;

const NODE_WIDTH = 240;
const NODE_HEIGHT = 96;
const CONTENT_LIMIT = 120;

export function nodeText(entry: Entry): string {
  if (entry.label !== null) return entry.label;

  const characters = Array.from(entry.content);
  if (characters.length <= CONTENT_LIMIT) return entry.content;
  return `${characters.slice(0, CONTENT_LIMIT - 1).join("").trimEnd()}…`;
}

export function layoutGraph(graph: GraphSnapshot): { nodes: EntryNode[]; edges: Edge[] } {
  const layout = new dagre.graphlib.Graph();
  layout.setDefaultEdgeLabel(() => ({}));
  layout.setGraph({ rankdir: "TB", ranksep: 90, nodesep: 50, marginx: 24, marginy: 24 });

  for (const entry of graph.entries) {
    layout.setNode(entry.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const edge of graph.edges) {
    layout.setEdge(edge.parent_id, edge.child_id);
  }

  dagre.layout(layout);

  const nodes = graph.entries.map((entry): EntryNode => {
    const position = layout.node(entry.id) as { x: number; y: number };
    return {
      id: entry.id,
      type: "entry",
      position: {
        x: position.x - NODE_WIDTH / 2,
        y: position.y - NODE_HEIGHT / 2,
      },
      data: { entry, text: nodeText(entry) },
    };
  });
  const edges = graph.edges.map(
    (edge): Edge => ({
      id: `${edge.parent_id}-${edge.child_id}`,
      source: edge.parent_id,
      target: edge.child_id,
    }),
  );

  return { nodes, edges };
}
