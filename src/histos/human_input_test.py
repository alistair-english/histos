"""Boundary behavior for adding human input."""

import pytest

from histos.graph import Author, ConversationGraph, EntryKind, EntryReference, ParentEdge
from histos.human_input import HumanInputError, add_human_entry


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


def test_human_cannot_add_an_agent_entry_kind() -> None:
    """Human insertion rejects kinds outside the current human capabilities."""
    with pytest.raises(HumanInputError):
        add_human_entry(
            ConversationGraph(),
            parent_id=None,
            kind=EntryKind.CONCEPT,
            content="An invalid human concept.",
            label="Concept",
        )
