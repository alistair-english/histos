"""Persistent graph state for a Histos workspace."""

from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

if TYPE_CHECKING:
    from pathlib import Path

Author = Literal["user", "agent"]
EntryKind = Literal["question", "message", "concept", "tool_call"]
UserEntryKind = Literal["question", "message"]
AgentEntryKind = Literal["concept", "question"]


class GraphError(ValueError):
    """Raised when a requested graph mutation is invalid."""


class Entry(BaseModel):
    """One entry in the ordered rooted tree."""

    model_config = ConfigDict(frozen=True)

    id: str
    parent_id: str | None
    author: Author
    kind: EntryKind
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)

    @field_validator("title", "content")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        """Strip graph text and reject whitespace-only values."""
        stripped = value.strip()
        if not stripped:
            msg = "Entry text cannot be blank"
            raise ValueError(msg)
        return stripped


class Graph(BaseModel):
    """The complete durable graph state."""

    model_config = ConfigDict(frozen=True)

    version: Literal[1] = 1
    entries: tuple[Entry, ...] = ()


class GraphStore:
    """Read and atomically update one workspace graph JSON file."""

    def __init__(self, workspace: Path) -> None:
        """Use ``workspace/.histos/graph.json`` for durable state."""
        self.workspace = workspace.resolve()
        self.path = self.workspace / ".histos" / "graph.json"
        self._lock = threading.RLock()

    def read(self) -> Graph:
        """Return the current graph, or an empty graph before first use."""
        with self._lock:
            if not self.path.exists():
                return Graph()
            try:
                return Graph.model_validate_json(self.path.read_text(encoding="utf-8"))
            except (OSError, ValidationError, json.JSONDecodeError) as exc:
                msg = f"Cannot read graph at {self.path}: {exc}"
                raise GraphError(msg) from exc

    def reset(self) -> Graph:
        """Delete the persisted graph and return a new empty graph."""
        with self._lock:
            self.path.unlink(missing_ok=True)
            return Graph()

    def add_user_entry(
        self,
        *,
        parent_id: str | None,
        kind: UserEntryKind,
        title: str,
        content: str,
    ) -> Entry:
        """Append a valid user entry and return it."""
        return self._add_entry(
            parent_id=parent_id,
            author="user",
            kind=kind,
            title=title,
            content=content,
        )

    def add_agent_entry(
        self,
        *,
        parent_id: str,
        kind: AgentEntryKind,
        title: str,
        content: str,
    ) -> Entry:
        """Append a valid agent entry and return it."""
        return self._add_entry(
            parent_id=parent_id,
            author="agent",
            kind=kind,
            title=title,
            content=content,
        )

    def _add_entry(
        self,
        *,
        parent_id: str | None,
        author: Author,
        kind: EntryKind,
        title: str,
        content: str,
    ) -> Entry:
        with self._lock:
            graph = self.read()
            self._validate_parent(graph, parent_id, author, kind)
            entry = _validated_entry(
                parent_id=parent_id,
                author=author,
                kind=kind,
                title=title,
                content=content,
            )
            self._write(Graph(entries=(*graph.entries, entry)))
            return entry

    @staticmethod
    def _validate_parent(
        graph: Graph,
        parent_id: str | None,
        author: Author,
        kind: EntryKind,
    ) -> None:
        if not graph.entries:
            if parent_id is not None or author != "user" or kind != "question":
                msg = "The first entry must be a root user question"
                raise GraphError(msg)
            return
        if parent_id is None:
            msg = "Only the first entry may be a root"
            raise GraphError(msg)
        if not any(entry.id == parent_id for entry in graph.entries):
            msg = f"Parent entry does not exist: {parent_id}"
            raise GraphError(msg)

    def _write(self, graph: Graph) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            graph.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


def _validated_entry(
    *,
    parent_id: str | None,
    author: Author,
    kind: EntryKind,
    title: str,
    content: str,
) -> Entry:
    try:
        return Entry(
            id=uuid4().hex,
            parent_id=parent_id,
            author=author,
            kind=kind,
            title=title,
            content=content,
        )
    except ValidationError as exc:
        msg = "Entry title and content must contain text"
        raise GraphError(msg) from exc
