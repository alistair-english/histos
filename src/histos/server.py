"""FastAPI application for the local Histos workspace."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from histos.codex import CodexGraphError, CodexGraphResponder
from histos.graph import Graph, GraphError, GraphStore, UserEntryKind


class CreateEntryRequest(BaseModel):
    """Fields accepted when the user adds an entry."""

    parent_id: str | None = None
    kind: UserEntryKind
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)


class RespondResponse(BaseModel):
    """Graph state and IDs added by one model response."""

    graph: Graph
    added_entry_ids: tuple[str, ...]


def create_app(workspace: Path | None = None) -> FastAPI:
    """Create an application scoped to one canonical workspace."""
    root = (workspace or Path.cwd()).resolve()
    store = GraphStore(root)
    responder = CodexGraphResponder(store)
    app = FastAPI(title="Histos", version="0.1.0")

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "workspace": str(root)}

    @app.get("/api/graph", response_model=Graph)
    async def get_graph() -> Graph:
        try:
            return store.read()
        except GraphError as exc:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc

    @app.delete("/api/graph", response_model=Graph)
    async def reset_graph() -> Graph:
        try:
            return store.reset()
        except OSError as exc:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc

    @app.post("/api/entries", response_model=Graph, status_code=status.HTTP_201_CREATED)
    async def create_entry(request: CreateEntryRequest) -> Graph:
        try:
            store.add_user_entry(
                parent_id=request.parent_id,
                kind=request.kind,
                title=request.title,
                content=request.content,
            )
            return store.read()
        except GraphError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    @app.post("/api/respond", response_model=RespondResponse)
    async def respond() -> RespondResponse:
        try:
            additions = await asyncio.to_thread(responder.respond)
            return RespondResponse(
                graph=store.read(),
                added_entry_ids=tuple(entry.id for entry in additions),
            )
        except CodexGraphError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    frontend = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    assets = frontend / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    index = frontend / "index.html"
    if not index.is_file():
        return

    @app.get("/", include_in_schema=False)
    async def frontend_index() -> FileResponse:
        return FileResponse(index)


app = create_app()
