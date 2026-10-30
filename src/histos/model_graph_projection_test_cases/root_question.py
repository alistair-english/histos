"""A graph containing one labeled human question."""

from histos.graph import ConversationGraph, EntryKind
from histos.human_graph_writing import add_human_entry


def build_graph() -> ConversationGraph:
    graph, _ = add_human_entry(
        ConversationGraph(),
        parent_id=None,
        kind=EntryKind.QUESTION,
        content="How should sessions work?",
        label="Session design",
    )
    return graph
