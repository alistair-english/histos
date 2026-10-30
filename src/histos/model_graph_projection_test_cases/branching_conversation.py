"""A labeled conversation with sibling and nested agent entries."""

from histos.agent_graph_writing import add_agent_entry
from histos.graph import ConversationGraph, EntryKind, EntryReference
from histos.human_graph_writing import add_human_entry


def build_graph() -> ConversationGraph:
    graph, root = add_human_entry(
        ConversationGraph(),
        parent_id=None,
        kind=EntryKind.QUESTION,
        content="How should authentication work?",
        label="Authentication",
    )
    graph, _ = add_agent_entry(
        graph,
        parent=root.reference,
        reference=EntryReference("token-authentication"),
        kind=EntryKind.CONCEPT,
        content="Use short-lived access tokens.",
        label="Token authentication",
    )
    graph, sessions = add_agent_entry(
        graph,
        parent=root.reference,
        reference=EntryReference("persistent-sessions"),
        kind=EntryKind.CONCEPT,
        content="Sessions should survive server restarts.",
        label="Persistent sessions",
    )
    graph, _ = add_agent_entry(
        graph,
        parent=sessions.reference,
        reference=EntryReference("session-duration"),
        kind=EntryKind.QUESTION,
        content="How long should a session remain valid?",
        label="Session duration",
    )
    return graph
