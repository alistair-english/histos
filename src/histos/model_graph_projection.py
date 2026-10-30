"""Project a conversation graph into model-readable Markdown."""

from collections import defaultdict

from histos.graph import ConversationGraph, Entry, EntryId


def project_graph_for_model(graph: ConversationGraph) -> str:
    """Return the complete graph as deterministic hierarchical Markdown."""
    snapshot = graph.snapshot()
    if not snapshot.entries:
        return ""

    entries_by_id = {entry.id: entry for entry in snapshot.entries}
    children_by_parent: defaultdict[EntryId, list[Entry]] = defaultdict(list)
    child_ids: set[EntryId] = set()
    for edge in snapshot.edges:
        children_by_parent[edge.parent_id].append(entries_by_id[edge.child_id])
        child_ids.add(edge.child_id)

    roots = sorted(
        (entry for entry in snapshot.entries if entry.id not in child_ids),
        key=_reference_sort_key,
    )
    lines: list[str] = []

    def append_entry(entry: Entry, depth: int) -> None:
        if lines:
            lines.append("")
        heading = "#" * min(depth + 1, 6)
        title = entry.label or f"@{entry.reference.value}"
        kind = entry.kind.value.replace("_", " ")
        lines.extend(
            (
                f"{heading} {title}",
                "",
                f"{entry.author.value.title()} {kind} · @{entry.reference.value}",
                "",
                entry.content,
            )
        )
        for child in sorted(children_by_parent[entry.id], key=_reference_sort_key):
            append_entry(child, depth + 1)

    for root in roots:
        append_entry(root, 0)

    return "\n".join(lines) + "\n"


def _reference_sort_key(entry: Entry) -> str:
    return entry.reference.value
