"""Tests for persistent graph state."""

from pathlib import Path

import pytest

from histos.graph import GraphError, GraphStore


def test_graph_persists_an_ordered_tree(tmp_path: Path) -> None:
    """Entries survive a new store instance and preserve append order."""
    store = GraphStore(tmp_path)
    root = store.add_user_entry(
        parent_id=None,
        kind="question",
        title="Authentication",
        content="How should authentication work?",
    )
    child = store.add_agent_entry(
        parent_id=root.id,
        kind="concept",
        title="Sessions",
        content="Use persistent refresh tokens.",
    )

    graph = GraphStore(tmp_path).read()

    assert graph.entries == (root, child)
    assert (tmp_path / ".histos" / "graph.json").is_file()


def test_graph_requires_one_user_question_root(tmp_path: Path) -> None:
    """No second root or agent-authored first root can be created."""
    store = GraphStore(tmp_path)

    with pytest.raises(GraphError, match="root user question"):
        store.add_agent_entry(
            parent_id="missing",
            kind="concept",
            title="Invalid",
            content="Invalid root",
        )

    root = store.add_user_entry(
        parent_id=None,
        kind="question",
        title="Root",
        content="Root content",
    )
    with pytest.raises(GraphError, match="Only the first entry"):
        store.add_user_entry(
            parent_id=None,
            kind="message",
            title="Second root",
            content="Not allowed",
        )
    assert store.read().entries == (root,)


def test_graph_rejects_unknown_parent(tmp_path: Path) -> None:
    """Every non-root entry must reference an existing entry."""
    store = GraphStore(tmp_path)
    store.add_user_entry(
        parent_id=None,
        kind="question",
        title="Root",
        content="Root content",
    )

    with pytest.raises(GraphError, match="does not exist"):
        store.add_user_entry(
            parent_id="missing",
            kind="message",
            title="Orphan",
            content="No parent",
        )
