"""Golden cases for model-readable graph projection."""

from collections.abc import Callable

from histos.graph import ConversationGraph
from histos.model_graph_projection_test_cases import branching_conversation, root_question

CASES: dict[str, Callable[[], ConversationGraph]] = {
    "root_question": root_question.build_graph,
    "branching_conversation": branching_conversation.build_graph,
}
