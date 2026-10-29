"""Tests for the workspace HTTP API."""

from pathlib import Path

from fastapi.testclient import TestClient

from histos.server import create_app


def test_entry_api_creates_root_and_child(tmp_path: Path) -> None:
    """The API returns the complete graph after each user addition."""
    with TestClient(create_app(tmp_path)) as client:
        root_response = client.post(
            "/api/entries",
            json={
                "parent_id": None,
                "kind": "question",
                "title": "Root",
                "content": "What should we build?",
            },
        )
        assert root_response.status_code == 201
        root_id = root_response.json()["entries"][0]["id"]

        child_response = client.post(
            "/api/entries",
            json={
                "parent_id": root_id,
                "kind": "message",
                "title": "Constraint",
                "content": "Keep it small.",
            },
        )
        assert child_response.status_code == 201
        assert len(child_response.json()["entries"]) == 2
        assert client.get("/api/graph").json() == child_response.json()

        reset_response = client.delete("/api/graph")
        assert reset_response.status_code == 200
        assert reset_response.json() == {"version": 1, "entries": []}
        assert not (tmp_path / ".histos" / "graph.json").exists()


def test_entry_api_reports_invalid_parent(tmp_path: Path) -> None:
    """Invalid graph mutations produce an actionable client error."""
    with TestClient(create_app(tmp_path)) as client:
        response = client.post(
            "/api/entries",
            json={
                "parent_id": "missing",
                "kind": "message",
                "title": "Orphan",
                "content": "No root exists.",
            },
        )

    assert response.status_code == 422
    assert "root user question" in response.json()["detail"]
