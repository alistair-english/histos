"""Boundary behavior for agent graph writing."""

import pytest

from histos.agent_graph_writing import AgentGraphWritingError, add_agent_entry
from histos.graph import Author, ConversationGraph, EntryKind, EntryReference, ParentEdge
from histos.human_graph_writing import add_human_entry


def test_agent_builds_a_hierarchy_with_semantic_references() -> None:
    """Agent additions can address existing and newly created entries by reference."""
    graph, root = add_human_entry(
        ConversationGraph(),
        parent_id=None,
        kind=EntryKind.QUESTION,
        content="How should sessions work?",
        label="Session design",
    )
    graph, concept = add_agent_entry(
        graph,
        parent=root.reference,
        reference=EntryReference("persistent-sessions"),
        kind=EntryKind.CONCEPT,
        content="Sessions should survive server restarts.",
        label="Persistent sessions",
    )
    graph, question = add_agent_entry(
        graph,
        parent=concept.reference,
        reference=EntryReference("session-duration"),
        kind=EntryKind.QUESTION,
        content="How long should a session remain valid?",
    )

    assert concept.author is Author.AGENT
    assert question.author is Author.AGENT
    assert graph.snapshot().edges == frozenset(
        (
            ParentEdge(parent_id=root.id, child_id=concept.id),
            ParentEdge(parent_id=concept.id, child_id=question.id),
        )
    )


def test_agent_cannot_add_an_unsupported_entry_kind() -> None:
    """Agent writing is limited to concepts and questions."""
    graph, root = add_human_entry(
        ConversationGraph(),
        parent_id=None,
        kind=EntryKind.QUESTION,
        content="What should happen next?",
        label="Next action",
    )

    with pytest.raises(AgentGraphWritingError):
        add_agent_entry(
            graph,
            parent=root.reference,
            reference=EntryReference("agent-message"),
            kind=EntryKind.MESSAGE,
            content="An unsupported agent message.",
        )
