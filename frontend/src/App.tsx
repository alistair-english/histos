import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { useEffect, useMemo, useState, type FormEvent } from "react";

type Author = "user" | "agent";
type EntryKind = "question" | "message" | "concept" | "tool_call";
type UserEntryKind = "question" | "message";

interface Entry {
  id: string;
  parent_id: string | null;
  author: Author;
  kind: EntryKind;
  title: string;
  content: string;
}

interface Graph {
  version: 1;
  entries: Entry[];
}

interface EntryNodeData extends Record<string, unknown> {
  entry: Entry;
  selected: boolean;
}

type EntryNode = Node<EntryNodeData, "entry">;

interface ApiErrorBody {
  detail?: unknown;
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as ApiErrorBody;
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // Keep the HTTP status when the body is not JSON.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

function EntryCard({ data }: NodeProps<EntryNode>) {
  const { entry, selected } = data;
  return (
    <article className={`entry-card ${entry.author} ${selected ? "selected" : ""}`}>
      <Handle type="target" position={Position.Top} />
      <div className="entry-meta">
        {entry.author} · {entry.kind}
      </div>
      <h2>{entry.title}</h2>
      <p>{entry.content}</p>
      <Handle type="source" position={Position.Bottom} />
    </article>
  );
}

const nodeTypes = { entry: EntryCard };

function graphElements(
  graph: Graph,
  selectedId: string | null,
): {
  nodes: EntryNode[];
  edges: Edge[];
} {
  const depths = new Map<string, number>();
  const columns = new Map<number, number>();
  const nodes = graph.entries.map((entry) => {
    const parentDepth = entry.parent_id === null ? -1 : (depths.get(entry.parent_id) ?? 0);
    const depth = parentDepth + 1;
    depths.set(entry.id, depth);
    const column = columns.get(depth) ?? 0;
    columns.set(depth, column + 1);
    return {
      id: entry.id,
      type: "entry" as const,
      position: { x: column * 330, y: depth * 230 },
      data: { entry, selected: entry.id === selectedId },
    };
  });
  const edges = graph.entries.flatMap((entry) =>
    entry.parent_id === null
      ? []
      : [
          {
            id: `${entry.parent_id}-${entry.id}`,
            source: entry.parent_id,
            target: entry.id,
            markerEnd: { type: MarkerType.ArrowClosed },
          },
        ],
  );
  return { nodes, edges };
}

export function App() {
  const [graph, setGraph] = useState<Graph>({ version: 1, entries: [] });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [kind, setKind] = useState<UserEntryKind>("message");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void requestJson<Graph>("/api/graph").then(
      (nextGraph) => {
        setGraph(nextGraph);
        setSelectedId((current) => current ?? nextGraph.entries[0]?.id ?? null);
      },
      (caught: unknown) => {
        setError(caught instanceof Error ? caught.message : String(caught));
      },
    );
  }, []);

  const elements = useMemo(() => graphElements(graph, selectedId), [graph, selectedId]);
  const isEmpty = graph.entries.length === 0;

  async function submitEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const nextGraph = await requestJson<Graph>("/api/entries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          parent_id: isEmpty ? null : selectedId,
          kind: isEmpty ? "question" : kind,
          title,
          content,
        }),
      });
      setGraph(nextGraph);
      setSelectedId(nextGraph.entries.at(-1)?.id ?? null);
      setTitle("");
      setContent("");
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  async function respond() {
    setBusy(true);
    setError(null);
    try {
      const result = await requestJson<{ graph: Graph }>("/api/respond", {
        method: "POST",
      });
      setGraph(result.graph);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  async function resetGraph() {
    if (!window.confirm("Delete every entry in this graph? This cannot be undone.")) return;
    setBusy(true);
    setError(null);
    try {
      const emptyGraph = await requestJson<Graph>("/api/graph", { method: "DELETE" });
      setGraph(emptyGraph);
      setSelectedId(null);
      setTitle("");
      setContent("");
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <header>
        <div>
          <span className="eyebrow">Local graph conversation</span>
          <h1>Histos</h1>
        </div>
        <div className="header-actions">
          <button className="reset" disabled={busy || isEmpty} onClick={() => void resetGraph()} type="button">
            Reset graph
          </button>
          <button className="respond" disabled={busy || isEmpty} onClick={() => void respond()} type="button">
            {busy ? "Working…" : "Respond"}
          </button>
        </div>
      </header>

      <section className="workspace">
        <div className="canvas">
          {isEmpty ? (
            <div className="empty-state">Create the root question to begin.</div>
          ) : (
            <ReactFlow
              fitView
              edges={elements.edges}
              nodes={elements.nodes}
              nodeTypes={nodeTypes}
              nodesDraggable={false}
              onNodeClick={(_event, node) => setSelectedId(node.id)}
            >
              <Background color="#30352c" gap={24} />
              <Controls />
            </ReactFlow>
          )}
        </div>

        <aside>
          <div>
            <span className="eyebrow">{isEmpty ? "Start" : "Selected parent"}</span>
            <strong>
              {isEmpty
                ? "Root question"
                : (graph.entries.find((entry) => entry.id === selectedId)?.title ?? "Choose a node")}
            </strong>
          </div>

          <form onSubmit={(event) => void submitEntry(event)}>
            {!isEmpty && (
              <label>
                Entry type
                <select value={kind} onChange={(event) => setKind(event.target.value as UserEntryKind)}>
                  <option value="message">Message</option>
                  <option value="question">Question</option>
                </select>
              </label>
            )}
            <label>
              Title
              <input
                required
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder={isEmpty ? "What should we explore?" : "Short label"}
              />
            </label>
            <label>
              Content
              <textarea
                required
                rows={7}
                value={content}
                onChange={(event) => setContent(event.target.value)}
                placeholder="Write the entry content…"
              />
            </label>
            <button disabled={busy || (!isEmpty && selectedId === null)} type="submit">
              {isEmpty ? "Create graph" : "Attach entry"}
            </button>
          </form>

          {error !== null && <div className="error">{error}</div>}
        </aside>
      </section>
    </main>
  );
}
