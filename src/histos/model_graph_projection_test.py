"""Golden-file behavior for model-readable graph projection."""

from collections.abc import Callable
from pathlib import Path

import pytest

from histos.graph import ConversationGraph
from histos.model_graph_projection import project_graph_for_model
from histos.model_graph_projection_test_cases import CASES

_CASES_DIRECTORY = Path(__file__).with_name("model_graph_projection_test_cases")


@pytest.mark.parametrize(("name", "build_graph"), CASES.items(), ids=tuple(CASES))
def test_model_graph_projection(
    name: str,
    build_graph: Callable[[], ConversationGraph],
) -> None:
    """Each graph projection matches its human-reviewable Markdown file."""
    expected_path = _CASES_DIRECTORY / f"{name}_expected.md"

    assert project_graph_for_model(build_graph()) == expected_path.read_text(encoding="utf-8")
