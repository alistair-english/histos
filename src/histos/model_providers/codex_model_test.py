"""Boundary behavior for the Codex model adapter."""

from collections.abc import Mapping

import pytest

from histos.agent_runtime import (
    AssistantTurn,
    JsonObject,
    ModelGenerationError,
    TextMessage,
    Tool,
    ToolCall,
    ToolExecution,
    ToolResultMessage,
)
from histos.model_providers.codex_model import (
    decode_codex_events,
    decode_codex_object,
    encode_codex_object_request,
    encode_codex_request,
)


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


def test_codex_object_request_requires_the_supplied_json_schema() -> None:
    """Structured generation uses strict schema output without agent tools."""
    schema: JsonObject = {
        "type": "object",
        "properties": {"reference": {"type": "string"}},
        "required": ["reference"],
        "additionalProperties": False,
    }

    request = encode_codex_object_request(
        model="codex-test-model",
        messages=(
            TextMessage(role="system", content="Generate entry metadata."),
            TextMessage(role="user", content="How should this be labeled?"),
        ),
        schema=schema,
    )

    assert request["instructions"] == "Generate entry metadata."
    assert request["input"] == [
        {
            "role": "user",
            "content": [{"type": "input_text", "text": "How should this be labeled?"}],
        }
    ]
    assert request["text"] == {
        "format": {
            "type": "json_schema",
            "name": "structured_output",
            "schema": schema,
            "strict": True,
        },
        "verbosity": "low",
    }
    assert "tools" not in request
    assert "tool_choice" not in request


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


def test_completed_codex_events_become_a_structured_object() -> None:
    """Streamed schema-constrained text crosses the provider boundary as an object."""
    events: tuple[JsonObject, ...] = (
        {"type": "response.output_text.delta", "delta": '{"reference":"structured'},
        {"type": "response.output_text.delta", "delta": '-generation","label":null}'},
        {"type": "response.completed"},
    )

    assert decode_codex_object(events) == {
        "reference": "structured-generation",
        "label": None,
    }


def test_structured_codex_response_must_be_an_object() -> None:
    """A provider response cannot escape the GenerateObject result contract."""
    events: tuple[JsonObject, ...] = (
        {"type": "response.output_text.delta", "delta": "[]"},
        {"type": "response.completed"},
    )

    with pytest.raises(ModelGenerationError, match="not an object"):
        decode_codex_object(events)
