"""Application behavior for adding human input to a conversation graph."""

from __future__ import annotations

from histos.graph import (
    UNCHANGED,
    Author,
    ConversationGraph,
    Entry,
    EntryId,
    EntryKind,
    EntryReference,
    Unchanged,
)


class HumanInputError(ValueError):
    """Raised when human input cannot be applied to the graph."""


def add_human_entry(
    graph: ConversationGraph,
    *,
    parent_id: EntryId | None,
    kind: EntryKind,
    content: str,
    label: str | None = None,
) -> tuple[ConversationGraph, Entry]:
    """Add human input while keeping its semantic reference hidden.

    A supplied label becomes the basis of a slug reference. Reference conflicts
    are resolved here because reference generation belongs to the submitter, not
    to the graph engine.
    """
    if kind not in (EntryKind.QUESTION, EntryKind.MESSAGE):
        msg = f"A human cannot add an entry of kind: {kind.value}"
        raise HumanInputError(msg)

    if label is None:
        # Give a small model the new content plus relevant context from `graph`,
        # including its intended parent. The model must always propose a semantic
        # reference. It may also propose a concise label for graph visualization,
        # but should omit the label when the content itself is already the best
        # display text, such as "yes" in response to a question. Humans should
        # never need to provide or edit the generated reference.
        msg = "Generating metadata for unlabeled human input is not implemented"
        raise NotImplementedError(msg)

    reference = _available_reference(graph, _slugify(label))
    return graph.add_entry(
        parent=parent_id,
        reference=reference,
        author=Author.USER,
        kind=kind,
        content=content,
        label=label,
    )


def edit_entry(
    graph: ConversationGraph,
    *,
    entry_id: EntryId,
    content: str | Unchanged = UNCHANGED,
    label: str | Unchanged | None = UNCHANGED,
) -> tuple[ConversationGraph, Entry]:
    """Apply human content and label edits without exposing the reference."""
    if isinstance(content, Unchanged) and isinstance(label, Unchanged):
        msg = "An entry edit must change content or label"
        raise HumanInputError(msg)

    reference: EntryReference | Unchanged = UNCHANGED
    if isinstance(label, str):
        reference = _available_reference(
            graph,
            _slugify(label),
            excluding=entry_id,
        )

    return graph.update_entry(
        entry_id=entry_id,
        reference=reference,
        content=content,
        label=label,
    )


def _available_reference(
    graph: ConversationGraph,
    reference_base: str,
    *,
    excluding: EntryId | None = None,
) -> EntryReference:
    unavailable = {entry.reference for entry in graph.snapshot().entries if entry.id != excluding}
    reference = EntryReference(reference_base)
    suffix = 2
    while reference in unavailable:
        reference = EntryReference(f"{reference_base}-{suffix}")
        suffix += 1
    return reference


def _slugify(label: str) -> str:
    parts: list[str] = []
    separator_pending = False

    for character in label.strip().casefold():
        if character.isalnum():
            if separator_pending and parts:
                parts.append("-")
            parts.append(character)
            separator_pending = False
        elif parts:
            separator_pending = True

    slug = "".join(parts)
    if not slug:
        msg = "A human entry label must contain letters or numbers"
        raise HumanInputError(msg)
    return slug
