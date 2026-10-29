"""Core conversation graph types and behavior."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4


class Author(StrEnum):
    """The author of a conversation entry."""

    USER = "user"
    AGENT = "agent"


class EntryKind(StrEnum):
    """The conversational role of an entry."""

    QUESTION = "question"
    MESSAGE = "message"
    CONCEPT = "concept"
    TOOL_CALL = "tool_call"


@dataclass(frozen=True)
class EntryId:
    """An opaque identity assigned to an entry by its graph."""

    value: UUID


@dataclass(frozen=True)
class EntryReference:
    """A semantic reference used to address an entry."""

    value: str

    def __post_init__(self) -> None:
        """Reject references that contain no visible text."""
        if not self.value.strip():
            msg = "Entry references must contain text"
            raise ValueError(msg)


@dataclass(frozen=True)
class Entry:
    """Content held by a conversation graph."""

    id: EntryId
    reference: EntryReference
    author: Author
    kind: EntryKind
    content: str
    label: str | None = None

    def __post_init__(self) -> None:
        """Require content and reject blank optional labels."""
        if not self.content.strip():
            msg = "Entry content must contain text"
            raise ValueError(msg)
        if self.label is not None and not self.label.strip():
            msg = "Entry labels must contain text when supplied"
            raise ValueError(msg)


@dataclass(frozen=True)
class ParentEdge:
    """A parent-child relationship between two entries."""

    parent_id: EntryId
    child_id: EntryId


@dataclass(frozen=True)
class GraphSnapshot:
    """An immutable external view of a conversation graph."""

    entries: frozenset[Entry]
    edges: frozenset[ParentEdge]


class GraphError(ValueError):
    """Base class for invalid graph operations."""


class RootError(GraphError):
    """Raised when an entry would create an invalid root."""


class UnknownParentError(GraphError):
    """Raised when a requested parent is absent from the graph."""


class ReferenceConflictError(GraphError):
    """Raised when an entry reference is already in use."""

    def __init__(self, conflicting_entry: Entry) -> None:
        """Expose the existing entry so the submitter can choose another reference."""
        self.conflicting_entry = conflicting_entry
        msg = f"Entry reference already exists: {conflicting_entry.reference.value}"
        super().__init__(msg)


type EntryLocator = EntryId | EntryReference


@dataclass(frozen=True)
class ConversationGraph:
    """An empty or rooted conversation graph."""

    _entries: frozenset[Entry] = frozenset()
    _edges: frozenset[ParentEdge] = frozenset()

    def snapshot(self) -> GraphSnapshot:
        """Return the entries and parent edges for projection by a boundary."""
        return GraphSnapshot(entries=self._entries, edges=self._edges)

    def add_entry(  # noqa: PLR0913
        self,
        *,
        parent: EntryLocator | None,
        reference: EntryReference,
        author: Author,
        kind: EntryKind,
        content: str,
        label: str | None = None,
    ) -> tuple[Self, Entry]:
        """Add an entry beneath an ID or semantic reference."""
        self._reject_reference_conflict(reference)
        parent_id = self._resolve_parent(parent)
        self._validate_root(parent_id=parent_id, author=author, kind=kind)

        entry = Entry(
            id=self._next_id(),
            reference=reference,
            author=author,
            kind=kind,
            content=content,
            label=label,
        )
        edges = self._edges
        if parent_id is not None:
            edges = edges.union((ParentEdge(parent_id=parent_id, child_id=entry.id),))

        return type(self)(_entries=self._entries.union((entry,)), _edges=edges), entry

    def _reject_reference_conflict(self, reference: EntryReference) -> None:
        for entry in self._entries:
            if entry.reference == reference:
                raise ReferenceConflictError(entry)

    def _resolve_parent(self, parent: EntryLocator | None) -> EntryId | None:
        if parent is None:
            return None
        for entry in self._entries:
            if isinstance(parent, EntryId) and entry.id == parent:
                return entry.id
            if isinstance(parent, EntryReference) and entry.reference == parent:
                return entry.id
        msg = f"Parent does not exist: {parent.value}"
        raise UnknownParentError(msg)

    def _validate_root(self, *, parent_id: EntryId | None, author: Author, kind: EntryKind) -> None:
        if not self._entries:
            if parent_id is not None:
                msg = "The first entry cannot have a parent"
                raise RootError(msg)
            if author is not Author.USER or kind is not EntryKind.QUESTION:
                msg = "The first entry must be a user question"
                raise RootError(msg)
            return
        if parent_id is None:
            msg = "A non-empty graph cannot accept another root"
            raise RootError(msg)

    def _next_id(self) -> EntryId:
        existing_ids = {entry.id for entry in self._entries}
        candidate = EntryId(uuid4())
        while candidate in existing_ids:
            candidate = EntryId(uuid4())
        return candidate
