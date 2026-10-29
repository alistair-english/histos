"""Boundary behavior for the conversation graph."""

from uuid import uuid4

import pytest

from histos.graph import (
    Author,
    ConversationGraph,
    EntryId,
    EntryKind,
    EntryReference,
    ParentEdge,
    ReferenceConflictError,
    RootError,
    UnknownParentError,
)


def test_entries_can_be_parented_by_id_or_reference() -> None:
    """Callers can use either graph-owned IDs or semantic references."""
    graph = ConversationGraph()
    graph, root = graph.add_entry(
        parent=None,
        reference=EntryReference("root-question"),
        author=Author.USER,
        kind=EntryKind.QUESTION,
        content="What should we build?",
    )
    graph, first_child = graph.add_entry(
        parent=root.id,
        reference=EntryReference("first-concept"),
        author=Author.AGENT,
        kind=EntryKind.CONCEPT,
        content="The first concept.",
    )
    graph, second_child = graph.add_entry(
        parent=root.reference,
        reference=EntryReference("second-concept"),
        author=Author.AGENT,
        kind=EntryKind.CONCEPT,
        content="The second concept.",
    )

    snapshot = graph.snapshot()

    assert snapshot.entries == frozenset((root, first_child, second_child))
    assert snapshot.edges == frozenset(
        (
            ParentEdge(parent_id=root.id, child_id=first_child.id),
            ParentEdge(parent_id=root.id, child_id=second_child.id),
        )
    )


def test_reference_conflict_reports_the_existing_entry() -> None:
    """A submitter receives the conflicting entry so it can choose another reference."""
    graph = ConversationGraph()
    graph, root = graph.add_entry(
        parent=None,
        reference=EntryReference("shared-reference"),
        author=Author.USER,
        kind=EntryKind.QUESTION,
        content="The root question.",
    )

    with pytest.raises(ReferenceConflictError) as raised:
        graph.add_entry(
            parent=root.id,
            reference=root.reference,
            author=Author.AGENT,
            kind=EntryKind.CONCEPT,
            content="Conflicting content.",
        )

    assert raised.value.conflicting_entry == root


def test_first_entry_must_be_a_root_user_question() -> None:
    """The initial graph permits only the current root entry semantics."""
    graph = ConversationGraph()

    with pytest.raises(RootError):
        graph.add_entry(
            parent=None,
            reference=EntryReference("agent-root"),
            author=Author.AGENT,
            kind=EntryKind.CONCEPT,
            content="An invalid root.",
        )


def test_non_empty_graph_rejects_another_root() -> None:
    """The current graph shape has at most one root."""
    graph = ConversationGraph()
    graph, _ = graph.add_entry(
        parent=None,
        reference=EntryReference("first-root"),
        author=Author.USER,
        kind=EntryKind.QUESTION,
        content="The first root.",
    )

    with pytest.raises(RootError):
        graph.add_entry(
            parent=None,
            reference=EntryReference("second-root"),
            author=Author.USER,
            kind=EntryKind.QUESTION,
            content="The second root.",
        )


def test_unknown_parent_id_or_reference_is_rejected() -> None:
    """Parent selectors must resolve to an existing entry."""
    graph = ConversationGraph()
    graph, _ = graph.add_entry(
        parent=None,
        reference=EntryReference("root"),
        author=Author.USER,
        kind=EntryKind.QUESTION,
        content="The root.",
    )

    for unknown_parent in (
        EntryId(uuid4()),
        EntryReference("missing"),
    ):
        with pytest.raises(UnknownParentError):
            graph.add_entry(
                parent=unknown_parent,
                reference=EntryReference(f"child-{unknown_parent.value}"),
                author=Author.AGENT,
                kind=EntryKind.CONCEPT,
                content="An orphaned entry.",
            )
