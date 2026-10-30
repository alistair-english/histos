"""Boundary behavior for human graph writing."""

import pytest

from histos.graph import Author, ConversationGraph, EntryKind, EntryReference, ParentEdge
from histos.human_graph_writing import (
    HumanGraphWritingError,
    add_human_entry,
    edit_entry,
)


def test_labeled_human_question_creates_the_root() -> None:
    """Human labels become references without exposing reference input."""
    graph, root = add_human_entry(
        ConversationGraph(),
        parent_id=None,
        kind=EntryKind.QUESTION,
        content="How should authentication work?",
        label="Authentication & Sessions",
    )

    assert root.author is Author.USER
    assert root.reference == EntryReference("authentication-sessions")
    assert graph.snapshot().entries == frozenset((root,))


def test_human_message_can_answer_an_entry() -> None:
    """Human messages attach through graph-owned internal IDs."""
    graph, root = add_human_entry(
        ConversationGraph(),
        parent_id=None,
        kind=EntryKind.QUESTION,
        content="Should the session persist?",
        label="Session persistence",
    )
    graph, answer = add_human_entry(
        graph,
        parent_id=root.id,
        kind=EntryKind.MESSAGE,
        content="Yes.",
        label="Answer",
    )

    assert graph.snapshot().edges == frozenset((ParentEdge(parent_id=root.id, child_id=answer.id),))


def test_conflicting_label_slug_is_renamed() -> None:
    """Repeated human labels receive distinct semantic references."""
    graph, root = add_human_entry(
        ConversationGraph(),
        parent_id=None,
        kind=EntryKind.QUESTION,
        content="Choose an approach.",
        label="Approach",
    )
    graph, first = add_human_entry(
        graph,
        parent_id=root.id,
        kind=EntryKind.MESSAGE,
        content="The first approach.",
        label="Candidate",
    )
    _, second = add_human_entry(
        graph,
        parent_id=root.id,
        kind=EntryKind.MESSAGE,
        content="The second approach.",
        label="Candidate",
    )

    assert first.reference == EntryReference("candidate")
    assert second.reference == EntryReference("candidate-2")


def test_human_can_edit_an_agent_entry_without_changing_its_identity_or_topology() -> None:
    """Human edits preserve provenance and graph-owned relationships."""
    graph, root = add_human_entry(
        ConversationGraph(),
        parent_id=None,
        kind=EntryKind.QUESTION,
        content="What approach should we take?",
        label="Approach question",
    )
    graph, concept = graph.add_entry(
        parent=root.id,
        reference=EntryReference("initial-concept"),
        author=Author.AGENT,
        kind=EntryKind.CONCEPT,
        content="Use the initial approach.",
        label="Initial concept",
    )
    original_edges = graph.snapshot().edges

    graph, edited = edit_entry(
        graph,
        entry_id=concept.id,
        content="Use the revised approach.",
        label="Revised concept",
    )

    assert edited.id == concept.id
    assert edited.author is Author.AGENT
    assert edited.kind is EntryKind.CONCEPT
    assert edited.content == "Use the revised approach."
    assert edited.reference == EntryReference("revised-concept")
    assert graph.snapshot().edges == original_edges


def test_human_can_remove_a_label_without_changing_other_entry_values() -> None:
    """An explicit null label differs from an omitted edit value."""
    graph, root = add_human_entry(
        ConversationGraph(),
        parent_id=None,
        kind=EntryKind.QUESTION,
        content="Should this keep its content?",
        label="Removable label",
    )

    _, edited = edit_entry(graph, entry_id=root.id, label=None)

    assert edited.label is None
    assert edited.content == root.content
    assert edited.reference == root.reference


def test_human_cannot_add_an_agent_entry_kind() -> None:
    """Human insertion rejects kinds outside the current human capabilities."""
    with pytest.raises(HumanGraphWritingError):
        add_human_entry(
            ConversationGraph(),
            parent_id=None,
            kind=EntryKind.CONCEPT,
            content="An invalid human concept.",
            label="Concept",
        )
