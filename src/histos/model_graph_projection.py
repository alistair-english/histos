"""Project a conversation graph into model-readable Markdown."""

from collections import defaultdict
from typing import Final

from histos.graph import ConversationGraph, Entry, EntryId

MODEL_GRAPH_FORMAT: Final = """\
The conversation is a rooted graph rendered as Markdown.

Each entry contains:
- A heading whose depth represents its graph depth.
- A metadata line: `<Author> <kind> · @reference`.
- For non-root entries: `· under @parent-reference`.
- The entry content after the metadata line.

Entries are rendered depth-first. Siblings are sorted by reference only for deterministic presentation;
sibling order has no semantic meaning.
"""


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

    def append_entry(entry: Entry, depth: int, parent: Entry | None) -> None:
        if lines:
            lines.append("")
        heading = "#" * min(depth + 1, 6)
        title = entry.label or f"@{entry.reference.value}"
        kind = entry.kind.value.replace("_", " ")
        metadata = f"{entry.author.value.title()} {kind} · @{entry.reference.value}"
        if parent is not None:
            metadata += f" · under @{parent.reference.value}"
        lines.extend(
            (
                f"{heading} {title}",
                "",
                metadata,
                "",
                entry.content,
            )
        )
        for child in sorted(children_by_parent[entry.id], key=_reference_sort_key):
            append_entry(child, depth + 1, entry)

    for root in roots:
        append_entry(root, 0, None)

    return "\n".join(lines) + "\n"


def _reference_sort_key(entry: Entry) -> str:
    return entry.reference.value
