"""HTTP boundary behavior for the local graph API."""

import asyncio
from collections.abc import Sequence
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from histos.agent_runtime import JsonObject, ModelGenerationError, TextMessage
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


def test_graph_state_is_empty_and_scoped_to_one_app() -> None:
    """Each local API starts with its own empty process-lifetime graph."""

    async def exercise_api() -> None:
        generate = _generate_from(({"reference": "root", "label": None},))
        first_app = create_app(generate_object=generate)
        second_app = create_app(generate_object=generate)
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
        app = create_app(
            generate_object=_generate_from(
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
        app = create_app(generate_object=generate)
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
        app = create_app(generate_object=fail_generation)
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
        app = create_app(generate_object=generate)
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
