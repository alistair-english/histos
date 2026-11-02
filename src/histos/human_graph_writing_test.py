"""Boundary behavior for human graph writing."""

import asyncio

import pytest

from histos.agent_runtime import JsonObject, TextMessage
from histos.graph import Author, ConversationGraph, EntryKind, EntryReference, ParentEdge
from histos.human_graph_writing import (
    HumanGraphWritingError,
    add_human_entry,
    edit_entry,
    submit_human_entry,
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


def test_human_entry_can_use_a_reference_without_a_label() -> None:
    """Resolved metadata can omit a label when content is suitable for display."""
    _, root = add_human_entry(
        ConversationGraph(),
        parent_id=None,
        kind=EntryKind.QUESTION,
        content="Use SQLite?",
        reference=EntryReference("use-sqlite"),
    )

    assert root.reference == EntryReference("use-sqlite")
    assert root.label is None


def test_human_entry_requires_a_label_or_reference() -> None:
    """Insertion cannot create an entry that other graph entries cannot address."""
    with pytest.raises(HumanGraphWritingError, match="requires a label or reference"):
        add_human_entry(
            ConversationGraph(),
            parent_id=None,
            kind=EntryKind.QUESTION,
            content="How should this be identified?",
        )


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


def test_labeled_submission_bypasses_metadata_generation() -> None:
    """Explicit human metadata does not spend a model request."""

    async def unexpected_generation(
        _messages: tuple[TextMessage, ...],
        _schema: JsonObject,
    ) -> JsonObject:
        pytest.fail("Labeled submission called the model")

    _, root = asyncio.run(
        submit_human_entry(
            ConversationGraph(),
            parent_id=None,
            kind=EntryKind.QUESTION,
            content="How should metadata work?",
            label="Metadata",
            generate_object=unexpected_generation,
        )
    )

    assert root.reference == EntryReference("metadata")
    assert root.label == "Metadata"


def test_unlabeled_submission_generates_contextual_metadata() -> None:
    """Human content and its graph position inform structured metadata generation."""
    graph, root = add_human_entry(
        ConversationGraph(),
        parent_id=None,
        kind=EntryKind.QUESTION,
        content="How should metadata work?",
        label="Metadata",
    )
    requests: list[tuple[tuple[TextMessage, ...], JsonObject]] = []

    async def generate_metadata(
        messages: tuple[TextMessage, ...],
        schema: JsonObject,
    ) -> JsonObject:
        requests.append((messages, schema))
        return {"reference": "yes", "label": None}

    _, answer = asyncio.run(
        submit_human_entry(
            graph,
            parent_id=root.id,
            kind=EntryKind.MESSAGE,
            content="Yes.",
            generate_object=generate_metadata,
        )
    )

    messages, schema = requests[0]
    assert "@metadata" in messages[1].content
    assert "Content:\nYes." in messages[1].content
    assert schema["required"] == ["reference", "label"]
    assert answer.reference == EntryReference("yes")
    assert answer.label is None


def test_generated_reference_conflicts_are_renamed() -> None:
    """Generated metadata uses the same deterministic conflict policy as labels."""
    graph, root = add_human_entry(
        ConversationGraph(),
        parent_id=None,
        kind=EntryKind.QUESTION,
        content="Choose an approach.",
        label="Approach",
    )

    async def generate_metadata(
        _messages: tuple[TextMessage, ...],
        _schema: JsonObject,
    ) -> JsonObject:
        return {"reference": "approach", "label": "Another approach"}

    _, answer = asyncio.run(
        submit_human_entry(
            graph,
            parent_id=root.id,
            kind=EntryKind.MESSAGE,
            content="Try another approach.",
            generate_object=generate_metadata,
        )
    )

    assert answer.reference == EntryReference("approach-2")
    assert answer.label == "Another approach"


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
