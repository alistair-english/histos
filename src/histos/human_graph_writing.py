"""Application behavior for human graph writing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from histos.agent_runtime import JsonObject, TextMessage
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
from histos.model_graph_projection import MODEL_GRAPH_FORMAT, project_graph_for_model

if TYPE_CHECKING:
    from histos.model_provider import GenerateObject

_METADATA_SCHEMA: JsonObject = {
    "type": "object",
    "properties": {
        "reference": {"type": "string", "minLength": 1},
        "label": {"type": ["string", "null"], "minLength": 1},
    },
    "required": ["reference", "label"],
    "additionalProperties": False,
}
_METADATA_INSTRUCTIONS = f"""\
Generate semantic metadata for human input being added to a conversation graph.
The reference must be a concise, stable identifier that describes the input.
A label is an optional short summary of the entry content.
Return null when the content is already short and clear enough to display directly.
Generate a label only when the content is long or unwieldy and a shorter summary would help.
Do not replace short content with a categorical label such as "Confirmation" or "Question".

Examples:
- "Yes." -> null
- "No, keep it local." -> null
- "Why?" -> null
- "Use SQLite." -> null
- "Store each immutable graph snapshot in a local SQLite database behind a repository boundary." ->
  "SQLite snapshot storage"

{MODEL_GRAPH_FORMAT}"""


class HumanGraphWritingError(ValueError):
    """Raised when a human graph-writing operation is invalid."""


def add_human_entry(
    graph: ConversationGraph,
    *,
    parent_id: EntryId | None,
    kind: EntryKind,
    content: str,
    reference: EntryReference | None = None,
    label: str | None = None,
) -> tuple[ConversationGraph, Entry]:
    """Add human input with an explicit or label-derived semantic reference."""
    _validate_human_kind(kind)
    if reference is None and label is None:
        msg = "A human entry requires a label or reference"
        raise HumanGraphWritingError(msg)

    reference_base = reference.value if reference is not None else _slugify(label or "")
    return graph.add_entry(
        parent=parent_id,
        reference=_available_reference(graph, reference_base),
        author=Author.USER,
        kind=kind,
        content=content,
        label=label,
    )


async def submit_human_entry(
    graph: ConversationGraph,
    *,
    parent_id: EntryId | None,
    kind: EntryKind,
    content: str,
    generate_object: GenerateObject,
    label: str | None = None,
) -> tuple[ConversationGraph, Entry]:
    """Add human input, generating semantic metadata when no label is supplied."""
    if label is not None:
        return add_human_entry(
            graph,
            parent_id=parent_id,
            kind=kind,
            content=content,
            label=label,
        )

    _validate_human_kind(kind)
    parent = "none; this entry will be the graph root"
    if parent_id is not None:
        parent = f"@{graph.get_entry(parent_id).reference.value}"
    projection = project_graph_for_model(graph) or "(empty graph)\n"
    result = await generate_object(
        (
            TextMessage(role="system", content=_METADATA_INSTRUCTIONS),
            TextMessage(
                role="user",
                content=(
                    "Generate metadata for this human entry.\n\n"
                    f"Kind: {kind.value}\n"
                    f"Parent: {parent}\n"
                    f"Content:\n{content}\n\n"
                    f"Current conversation graph:\n\n{projection}"
                ),
            ),
        ),
        _METADATA_SCHEMA,
    )
    reference = EntryReference(_required_generated_string(result, "reference"))
    generated_label = _optional_generated_string(result, "label")
    return add_human_entry(
        graph,
        parent_id=parent_id,
        kind=kind,
        content=content,
        reference=reference,
        label=generated_label,
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
        raise HumanGraphWritingError(msg)

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


def _validate_human_kind(kind: EntryKind) -> None:
    if kind not in (EntryKind.QUESTION, EntryKind.MESSAGE):
        msg = f"A human cannot add an entry of kind: {kind.value}"
        raise HumanGraphWritingError(msg)


def _required_generated_string(result: JsonObject, name: str) -> str:
    value = result.get(name)
    if not isinstance(value, str):
        msg = f"Generated human entry metadata '{name}' must be a string"
        raise HumanGraphWritingError(msg)
    return value


def _optional_generated_string(result: JsonObject, name: str) -> str | None:
    value = result.get(name)
    if value is not None and not isinstance(value, str):
        msg = f"Generated human entry metadata '{name}' must be a string or null"
        raise HumanGraphWritingError(msg)
    return value


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
        raise HumanGraphWritingError(msg)
    return slug
