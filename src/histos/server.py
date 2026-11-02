"""Local HTTP API for the current conversation graph."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal
from uuid import UUID  # noqa: TC003 - Pydantic resolves this annotation at runtime

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from histos.agent_runtime import ModelGenerationError
from histos.credentials import FileCredentialStore
from histos.graph import Author, ConversationGraph, EntryId, EntryKind, GraphError
from histos.human_graph_writing import HumanGraphWritingError, submit_human_entry
from histos.model_providers import CodexProvider

if TYPE_CHECKING:
    from histos.model_provider import GenerateObject


class AddEntryRequest(BaseModel):
    """Human entry fields accepted from the browser."""

    model_config = ConfigDict(frozen=True)

    parent_id: UUID | None
    kind: Literal["question", "message"]
    content: str = Field(min_length=1)


class EntryResponse(BaseModel):
    """One browser-visible graph entry."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    author: Author
    kind: EntryKind
    content: str
    label: str | None


class EdgeResponse(BaseModel):
    """One browser-visible parent-child relationship."""

    model_config = ConfigDict(frozen=True)

    parent_id: UUID
    child_id: UUID


class GraphResponse(BaseModel):
    """Complete browser-visible state of the current graph."""

    model_config = ConfigDict(frozen=True)

    entries: tuple[EntryResponse, ...]
    edges: tuple[EdgeResponse, ...]


def create_app(*, generate_object: GenerateObject | None = None) -> FastAPI:
    """Create a local API with one process-lifetime conversation graph."""
    object_generator = _default_generate_object() if generate_object is None else generate_object
    current_graph = ConversationGraph()
    write_lock = asyncio.Lock()
    api = FastAPI(title="Histos", version="0.1.0")

    @api.get("/api/graph", response_model=GraphResponse)
    async def get_graph() -> GraphResponse:
        return _graph_response(current_graph)

    @api.post("/api/entries", response_model=GraphResponse, status_code=status.HTTP_201_CREATED)
    async def create_entry(request: AddEntryRequest) -> GraphResponse:
        nonlocal current_graph
        if not request.content.strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Entry content must contain text")

        async with write_lock:
            try:
                next_graph, _ = await submit_human_entry(
                    current_graph,
                    parent_id=EntryId(request.parent_id) if request.parent_id is not None else None,
                    kind=EntryKind(request.kind),
                    content=request.content,
                    generate_object=object_generator,
                )
            except ModelGenerationError as error:
                raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error
            except (GraphError, HumanGraphWritingError) as error:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error

            current_graph = next_graph
            return _graph_response(current_graph)

    return api


def _graph_response(graph: ConversationGraph) -> GraphResponse:
    snapshot = graph.snapshot()
    entries = tuple(
        EntryResponse(
            id=entry.id.value,
            author=entry.author,
            kind=entry.kind,
            content=entry.content,
            label=entry.label,
        )
        for entry in sorted(snapshot.entries, key=lambda entry: str(entry.id.value))
    )
    edges = tuple(
        EdgeResponse(parent_id=edge.parent_id.value, child_id=edge.child_id.value)
        for edge in sorted(snapshot.edges, key=lambda edge: (str(edge.parent_id.value), str(edge.child_id.value)))
    )
    return GraphResponse(entries=entries, edges=edges)


def _default_generate_object() -> GenerateObject:
    provider = CodexProvider(FileCredentialStore())
    return provider.generate_object(provider.get_models()[0])


app = create_app()
