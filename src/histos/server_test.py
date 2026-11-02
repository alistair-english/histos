"""HTTP boundary behavior for the local graph API."""

import asyncio
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from histos.agent_runtime import (
    AssistantTurn,
    GenerateTurn,
    JsonObject,
    ModelGenerationError,
    ModelMessage,
    TextMessage,
    Tool,
    ToolCall,
)
from histos.model_provider import GenerateObject
from histos.server import create_app


def _generate_from(results: Sequence[JsonObject]) -> GenerateObject:
    remaining = iter(results)

    async def generate(
        _messages: tuple[TextMessage, ...],
        _schema: JsonObject,
    ) -> JsonObject:
        return next(remaining)

    return generate


async def _unexpected_turn(
    _messages: tuple[ModelMessage, ...],
    _tools: tuple[Tool, ...],
) -> AssistantTurn:
    msg = "Agent generation was not expected"
    raise AssertionError(msg)


def _test_app(
    generate_object: GenerateObject,
    *,
    generate_turn: GenerateTurn = _unexpected_turn,
    frontend_directory: Path | None = None,
) -> FastAPI:
    return create_app(
        generate_object=generate_object,
        generate_turn=generate_turn,
        frontend_directory=frontend_directory,
    )


def test_built_frontend_and_api_share_one_origin(tmp_path: Path) -> None:
    """The local app serves the browser entry point without shadowing its API."""
    (tmp_path / "index.html").write_text("<h1>Histos</h1>")

    async def exercise_app() -> None:
        app = _test_app(_generate_from(()), frontend_directory=tmp_path)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            frontend = await client.get("/")
            graph = await client.get("/api/graph")

        assert frontend.status_code == 200
        assert frontend.text == "<h1>Histos</h1>"
        assert graph.json() == {"entries": [], "edges": []}

    asyncio.run(exercise_app())


def test_graph_state_is_empty_and_scoped_to_one_app() -> None:
    """Each local API starts with its own empty process-lifetime graph."""

    async def exercise_api() -> None:
        generate = _generate_from(({"reference": "root", "label": None},))
        first_app = _test_app(generate)
        second_app = _test_app(generate)
        async with (
            AsyncClient(transport=ASGITransport(app=first_app), base_url="http://test") as first,
            AsyncClient(transport=ASGITransport(app=second_app), base_url="http://test") as second,
        ):
            assert (await first.get("/api/graph")).json() == {"entries": [], "edges": []}
            created = await first.post(
                "/api/entries",
                json={"parent_id": None, "kind": "question", "content": "A root question?"},
            )

            assert created.status_code == 201
            assert len(created.json()["entries"]) == 1
            assert (await second.get("/api/graph")).json() == {"entries": [], "edges": []}

    asyncio.run(exercise_api())


def test_entries_and_edges_cross_the_api_without_semantic_references() -> None:
    """The browser receives complete graph topology but not model-facing references."""

    async def exercise_api() -> None:
        app = _test_app(
            _generate_from(
                (
                    {"reference": "persistence", "label": "Persistence"},
                    {"reference": "use-sqlite", "label": None},
                )
            )
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            root_response = await client.post(
                "/api/entries",
                json={"parent_id": None, "kind": "question", "content": "How should persistence work?"},
            )
            root = root_response.json()["entries"][0]
            child_response = await client.post(
                "/api/entries",
                json={"parent_id": root["id"], "kind": "message", "content": "Use SQLite."},
            )
            body = child_response.json()

            assert child_response.status_code == 201
            assert {entry["kind"] for entry in body["entries"]} == {"question", "message"}
            assert {entry["label"] for entry in body["entries"]} == {"Persistence", None}
            assert all(set(entry) == {"id", "author", "kind", "content", "label"} for entry in body["entries"])
            child = next(entry for entry in body["entries"] if entry["kind"] == "message")
            assert body["edges"] == [{"parent_id": root["id"], "child_id": child["id"]}]
            assert (await client.get("/api/graph")).json() == body

    asyncio.run(exercise_api())


def test_agent_response_extends_the_graph_and_crosses_the_api() -> None:
    """One browser request publishes the complete graph produced by an agent run."""
    turns = iter(
        (
            AssistantTurn(
                tool_calls=(
                    ToolCall(
                        call_id="addition",
                        name="add_concept",
                        arguments={
                            "parent": "root",
                            "reference": "agent-answer",
                            "content": "The agent extends the graph.",
                            "label": "Agent answer",
                        },
                    ),
                )
            ),
            AssistantTurn(tool_calls=(ToolCall(call_id="finish", name="finish_response", arguments={}),)),
        )
    )

    async def generate_turn(
        _messages: tuple[ModelMessage, ...],
        _tools: tuple[Tool, ...],
    ) -> AssistantTurn:
        return next(turns)

    async def exercise_api() -> None:
        app = _test_app(
            _generate_from(({"reference": "root", "label": None},)),
            generate_turn=generate_turn,
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/api/entries",
                json={"parent_id": None, "kind": "question", "content": "Can an agent respond?"},
            )
            response = await client.post("/api/respond")
            body = response.json()

            assert response.status_code == 200
            assert body["error"] is None
            assert {entry["author"] for entry in body["graph"]["entries"]} == {"user", "agent"}
            assert len(body["graph"]["edges"]) == 1
            assert (await client.get("/api/graph")).json() == body["graph"]

    asyncio.run(exercise_api())


def test_invalid_browser_input_is_rejected_before_generation() -> None:
    """Malformed IDs, unsupported kinds, and blank content do not reach the model."""
    calls = 0

    async def generate(
        _messages: tuple[TextMessage, ...],
        _schema: JsonObject,
    ) -> JsonObject:
        nonlocal calls
        calls += 1
        return {"reference": "unused", "label": None}

    async def exercise_api() -> None:
        app = _test_app(generate)
        invalid_requests = (
            {"parent_id": "not-a-uuid", "kind": "message", "content": "Content"},
            {"parent_id": None, "kind": "concept", "content": "Content"},
            {"parent_id": None, "kind": "question", "content": "   "},
            {"parent_id": str(uuid4()), "kind": "message", "content": "Content"},
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            responses = [await client.post("/api/entries", json=request) for request in invalid_requests]

        assert all(response.status_code == 422 for response in responses)

    asyncio.run(exercise_api())
    assert calls == 0


def test_model_failure_preserves_the_current_graph() -> None:
    """A failed metadata request cannot publish a partial graph update."""

    async def fail_generation(
        _messages: tuple[TextMessage, ...],
        _schema: JsonObject,
    ) -> JsonObject:
        msg = "Provider unavailable"
        raise ModelGenerationError(msg)

    async def exercise_api() -> None:
        app = _test_app(fail_generation)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/entries",
                json={"parent_id": None, "kind": "question", "content": "Will this fail?"},
            )

            assert response.status_code == 502
            assert response.json() == {"detail": "Provider unavailable"}
            assert (await client.get("/api/graph")).json() == {"entries": [], "edges": []}

    asyncio.run(exercise_api())


def test_concurrent_submissions_do_not_overwrite_each_other() -> None:
    """Serialized writes retain both children submitted from the same graph state."""
    calls = 0

    async def generate(
        _messages: tuple[TextMessage, ...],
        _schema: JsonObject,
    ) -> JsonObject:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return {"reference": f"entry-{calls}", "label": None}

    async def exercise_api() -> None:
        app = _test_app(generate)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            root_response = await client.post(
                "/api/entries",
                json={"parent_id": None, "kind": "question", "content": "Choose two children?"},
            )
            root_id = root_response.json()["entries"][0]["id"]
            responses = await asyncio.gather(
                client.post(
                    "/api/entries",
                    json={"parent_id": root_id, "kind": "message", "content": "First child."},
                ),
                client.post(
                    "/api/entries",
                    json={"parent_id": root_id, "kind": "message", "content": "Second child."},
                ),
            )
            graph = (await client.get("/api/graph")).json()

        assert [response.status_code for response in responses] == [201, 201]
        assert len(graph["entries"]) == 3
        assert len(graph["edges"]) == 2

    asyncio.run(exercise_api())
