"""Boundary behavior for agent responses to a conversation graph."""

import asyncio

from histos.agent_graph_response import respond_to_graph
from histos.agent_runtime import (
    AssistantTurn,
    ModelMessage,
    TextMessage,
    Tool,
    ToolCall,
    ToolResultMessage,
)
from histos.graph import ConversationGraph, EntryKind, EntryReference
from histos.human_graph_writing import add_human_entry


def _root_graph() -> ConversationGraph:
    graph, _ = add_human_entry(
        ConversationGraph(),
        parent_id=None,
        kind=EntryKind.QUESTION,
        content="How should responses work?",
        label="Response question",
    )
    return graph


def test_agent_response_adds_to_a_graph_until_finished() -> None:
    """A finished response returns a new graph after feeding tool results back."""
    original_graph = _root_graph()
    model_inputs: list[tuple[ModelMessage, ...]] = []

    async def generate_turn(
        messages: tuple[ModelMessage, ...],
        tools: tuple[Tool, ...],
    ) -> AssistantTurn:
        model_inputs.append(messages)
        assert tuple(tool.name for tool in tools) == (
            "add_concept",
            "ask_question",
            "finish_response",
        )
        if len(model_inputs) == 1:
            assert isinstance(messages[-1], TextMessage)
            assert "@response-question" in messages[-1].content
            return AssistantTurn(
                tool_calls=(
                    ToolCall(
                        call_id="addition",
                        name="add_concept",
                        arguments={
                            "parent": "response-question",
                            "reference": "ephemeral-response",
                            "content": "Each response uses a fresh agent run.",
                            "label": "Ephemeral response",
                        },
                    ),
                )
            )

        assert messages[-1] == ToolResultMessage(
            tool_call_id="addition",
            output={
                "status": "added",
                "reference": "ephemeral-response",
                "parent": "response-question",
            },
        )
        return AssistantTurn(tool_calls=(ToolCall(call_id="finish", name="finish_response", arguments={}),))

    updated_graph, error = asyncio.run(respond_to_graph(original_graph, generate_turn=generate_turn))

    assert error is None
    assert updated_graph.get_entry(EntryReference("ephemeral-response")).content == (
        "Each response uses a fresh agent run."
    )
    assert len(original_graph.snapshot().entries) == 1


def test_expected_runtime_failure_returns_the_partially_updated_graph() -> None:
    """Accepted graph additions remain available when the agent run fails."""
    turns = 0

    async def generate_turn(
        _messages: tuple[ModelMessage, ...],
        _tools: tuple[Tool, ...],
    ) -> AssistantTurn:
        nonlocal turns
        turns += 1
        if turns == 1:
            return AssistantTurn(
                tool_calls=(
                    ToolCall(
                        call_id="addition",
                        name="ask_question",
                        arguments={
                            "parent": "response-question",
                            "reference": "response-duration",
                            "content": "How long may a response run?",
                        },
                    ),
                )
            )
        return AssistantTurn(text="This plaintext response is invalid.")

    updated_graph, error = asyncio.run(respond_to_graph(_root_graph(), generate_turn=generate_turn))

    assert error is not None
    assert updated_graph.get_entry(EntryReference("response-duration")).kind is EntryKind.QUESTION
