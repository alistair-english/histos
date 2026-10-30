"""Application behavior for agent graph writing."""

from histos.graph import Author, ConversationGraph, Entry, EntryKind, EntryReference


class AgentGraphWritingError(ValueError):
    """Raised when an agent graph-writing operation is invalid."""


def add_agent_entry(
    graph: ConversationGraph,
    *,
    parent: EntryReference,
    reference: EntryReference,
    kind: EntryKind,
    content: str,
    label: str | None = None,
) -> tuple[ConversationGraph, Entry]:
    """Add an agent concept or question beneath an existing entry."""
    if kind not in (EntryKind.CONCEPT, EntryKind.QUESTION):
        msg = f"An agent cannot add an entry of kind: {kind.value}"
        raise AgentGraphWritingError(msg)

    return graph.add_entry(
        parent=parent,
        reference=reference,
        author=Author.AGENT,
        kind=kind,
        content=content,
        label=label,
    )
