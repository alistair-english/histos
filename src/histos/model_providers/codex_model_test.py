"""Boundary behavior for the Codex model adapter."""

from collections.abc import Mapping

from histos.agent_runtime import (
    AssistantTurn,
    JsonObject,
    TextMessage,
    Tool,
    ToolCall,
    ToolExecution,
    ToolResultMessage,
)
from histos.model_providers.codex_model import decode_codex_events, encode_codex_request


def test_codex_request_contains_the_ephemeral_tool_transcript() -> None:
    """A later provider turn receives system context, calls, and their results."""

    async def unused_executor(_arguments: Mapping[str, object]) -> ToolExecution:
        return ToolExecution(output=None)

    request = encode_codex_request(
        model="codex-test-model",
        messages=(
            TextMessage(role="system", content="Use graph tools."),
            TextMessage(role="user", content="The projected graph."),
            AssistantTurn(
                tool_calls=(
                    ToolCall(
                        call_id="call-1",
                        name="add_concept",
                        arguments={"content": "Ephemeral runs"},
                    ),
                )
            ),
            ToolResultMessage(
                tool_call_id="call-1",
                output={"status": "added", "reference": "ephemeral-runs"},
            ),
        ),
        tools=(
            Tool(
                name="add_concept",
                description="Add a concept.",
                input_schema={"type": "object"},
                execute=unused_executor,
            ),
        ),
    )

    assert request["model"] == "codex-test-model"
    assert request["instructions"] == "Use graph tools."
    assert request["input"] == [
        {
            "role": "user",
            "content": [{"type": "input_text", "text": "The projected graph."}],
        },
        {
            "type": "function_call",
            "call_id": "call-1",
            "name": "add_concept",
            "arguments": '{"content":"Ephemeral runs"}',
        },
        {
            "type": "function_call_output",
            "call_id": "call-1",
            "output": '{"status":"added","reference":"ephemeral-runs"}',
        },
    ]
    assert request["tools"] == [
        {
            "type": "function",
            "name": "add_concept",
            "description": "Add a concept.",
            "parameters": {"type": "object"},
            "strict": False,
        }
    ]


def test_completed_codex_events_become_an_assistant_tool_turn() -> None:
    """Streamed reasoning, text, and function calls cross the provider boundary."""
    events: tuple[JsonObject, ...] = (
        {"type": "response.reasoning_summary_text.delta", "delta": "I should add "},
        {"type": "response.reasoning_summary_text.delta", "delta": "a concept."},
        {"type": "response.output_text.delta", "delta": "Hidden plaintext"},
        {
            "type": "response.output_item.done",
            "item": {
                "type": "function_call",
                "call_id": "call-1",
                "name": "add_concept",
                "arguments": '{"parent":"root","content":"A concept","reference":"concept"}',
            },
        },
        {"type": "response.completed"},
    )

    turn = decode_codex_events(events)

    assert turn == AssistantTurn(
        tool_calls=(
            ToolCall(
                call_id="call-1",
                name="add_concept",
                arguments={
                    "parent": "root",
                    "content": "A concept",
                    "reference": "concept",
                },
            ),
        ),
        text="Hidden plaintext",
        reasoning="I should add a concept.",
    )
