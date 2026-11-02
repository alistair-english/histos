import { Handle, Position, ReactFlow, type NodeProps } from "@xyflow/react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  emptyDraft,
  overrideDraftKind,
  updateDraftContent,
  type EntryDraft,
  type UserEntryKind,
} from "./draft.ts";
import {
  layoutGraph,
  type Entry,
  type EntryNode,
  type GraphSnapshot,
} from "./graph.ts";

interface ApiErrorBody {
  detail?: unknown;
}

interface AgentResponse {
  graph: GraphSnapshot;
  error: string | null;
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as ApiErrorBody;
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // Keep the HTTP status when the response body is not JSON.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
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
  const [draft, setDraft] = useState<EntryDraft>(emptyDraft);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void requestJson<GraphSnapshot>("/api/graph").then(setGraph, (caught: unknown) => {
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
  const isEmpty = graph.entries.length === 0;
  const needsParent = !isEmpty && selectedEntry === undefined;
  const displayedKind: UserEntryKind = isEmpty ? "question" : draft.kind;

  async function submitEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (needsParent || !draft.content.trim()) return;

    setBusy(true);
    setError(null);
    try {
      const existingIds = new Set(graph.entries.map((entry) => entry.id));
      const nextGraph = await requestJson<GraphSnapshot>("/api/entries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          parent_id: isEmpty ? null : selectedId,
          kind: displayedKind,
          content: draft.content,
        }),
      });
      const createdEntry = nextGraph.entries.find((entry) => !existingIds.has(entry.id));
      setGraph(nextGraph);
      setSelectedId(createdEntry?.id ?? selectedId);
      setDraft(emptyDraft);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  async function respondToGraph() {
    setBusy(true);
    setError(null);
    try {
      const response = await requestJson<AgentResponse>("/api/respond", { method: "POST" });
      setGraph(response.graph);
      setError(response.error);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

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
          <p>{isEmpty ? "Create a root question to begin." : "Select a node to read it and add a child."}</p>
        ) : (
          <article>
            <small>
              {selectedEntry.author} · {selectedEntry.kind}
            </small>
            <p>{selectedEntry.content}</p>
          </article>
        )}

        <button
          className="respond"
          disabled={busy || isEmpty}
          onClick={() => void respondToGraph()}
          type="button"
        >
          Respond
        </button>

        <form onSubmit={(event) => void submitEntry(event)}>
          <label>
            Kind
            <select
              disabled={isEmpty || busy || needsParent}
              value={displayedKind}
              onChange={(event) =>
                setDraft((current) => overrideDraftKind(current, event.target.value as UserEntryKind))
              }
            >
              <option value="message">Message</option>
              <option value="question">Question</option>
            </select>
          </label>
          <label>
            Content
            <textarea
              disabled={busy || needsParent}
              rows={7}
              value={draft.content}
              onChange={(event) => setDraft((current) => updateDraftContent(current, event.target.value))}
            />
          </label>
          <button disabled={busy || needsParent || !draft.content.trim()} type="submit">
            {isEmpty ? "Create root" : "Add entry"}
          </button>
        </form>

        {error !== null && <p role="alert">{error}</p>}
      </aside>
    </main>
  );
}
