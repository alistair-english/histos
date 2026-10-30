"""Boundary behavior for the ephemeral agent runtime."""

import asyncio
from collections.abc import Mapping

import pytest

from histos.agent_runtime import (
    AgentTurnLimitError,
    AssistantTurn,
    ModelMessage,
    PlaintextViolationLimitError,
    TextMessage,
    Tool,
    ToolCall,
    ToolExecution,
    ToolExecutor,
    ToolResultMessage,
    run_agent,
)

_PLAINTEXT_FEEDBACK = (
    "Protocol error: plaintext is not visible to the user. Write all useful content through graph tools."
)


def _tool(name: str, execute: ToolExecutor) -> Tool:
    return Tool(name=name, description=f"Execute {name}.", input_schema={}, execute=execute)


def test_agent_returns_tool_results_to_the_model_until_termination() -> None:
    """A tool result becomes context for the model turn that finishes the run."""
    model_inputs: list[tuple[ModelMessage, ...]] = []
    additions: list[Mapping[str, object]] = []

    async def generate_turn(
        messages: tuple[ModelMessage, ...],
        tools: tuple[Tool, ...],
    ) -> AssistantTurn:
        model_inputs.append(messages)
        assert tuple(tool.name for tool in tools) == ("add_concept", "finish_response")
        if len(model_inputs) == 1:
            return AssistantTurn(
                tool_calls=(
                    ToolCall(
                        call_id="addition",
                        name="add_concept",
                        arguments={"content": "Sessions should persist."},
                    ),
                )
            )
        return AssistantTurn(tool_calls=(ToolCall(call_id="finish", name="finish_response", arguments={}),))

    async def add_concept(arguments: Mapping[str, object]) -> ToolExecution:
        additions.append(arguments)
        return ToolExecution(output={"status": "added", "reference": "persistent-sessions"})

    async def finish_response(_arguments: Mapping[str, object]) -> ToolExecution:
        return ToolExecution(output={"status": "finished"}, terminate=True)

    asyncio.run(
        run_agent(
            generate_turn=generate_turn,
            messages=(TextMessage(role="user", content="The projected graph."),),
            tools=(
                _tool("add_concept", add_concept),
                _tool("finish_response", finish_response),
            ),
        )
    )

    assert additions == [{"content": "Sessions should persist."}]
    assert model_inputs[1][-1] == ToolResultMessage(
        tool_call_id="addition",
        output={"status": "added", "reference": "persistent-sessions"},
    )


def test_terminating_tool_skips_later_calls_in_the_same_turn() -> None:
    """Sequential execution stops at the first tool that requests termination."""
    executions: list[str] = []

    async def generate_turn(
        _messages: tuple[ModelMessage, ...],
        _tools: tuple[Tool, ...],
    ) -> AssistantTurn:
        return AssistantTurn(
            tool_calls=(
                ToolCall(call_id="before", name="record", arguments={"value": "before"}),
                ToolCall(call_id="finish", name="finish_response", arguments={}),
                ToolCall(call_id="after", name="record", arguments={"value": "after"}),
            )
        )

    async def record(arguments: Mapping[str, object]) -> ToolExecution:
        executions.append(str(arguments["value"]))
        return ToolExecution(output={"status": "recorded"})

    async def finish_response(_arguments: Mapping[str, object]) -> ToolExecution:
        executions.append("finish")
        return ToolExecution(output={"status": "finished"}, terminate=True)

    asyncio.run(
        run_agent(
            generate_turn=generate_turn,
            messages=(),
            tools=(
                _tool("record", record),
                _tool("finish_response", finish_response),
            ),
        )
    )

    assert executions == ["before", "finish"]


def test_plaintext_feedback_overrides_termination_and_allows_correction() -> None:
    """Useful plaintext is rejected even when its turn calls the terminating tool."""
    model_inputs: list[tuple[ModelMessage, ...]] = []

    async def generate_turn(
        messages: tuple[ModelMessage, ...],
        _tools: tuple[Tool, ...],
    ) -> AssistantTurn:
        model_inputs.append(messages)
        if len(model_inputs) == 1:
            return AssistantTurn(
                text="This response would not be visible.",
                tool_calls=(ToolCall(call_id="premature", name="finish_response", arguments={}),),
            )
        return AssistantTurn(tool_calls=(ToolCall(call_id="corrected", name="finish_response", arguments={}),))

    async def finish_response(_arguments: Mapping[str, object]) -> ToolExecution:
        return ToolExecution(output={"status": "finished"}, terminate=True)

    asyncio.run(
        run_agent(
            generate_turn=generate_turn,
            messages=(),
            tools=(_tool("finish_response", finish_response),),
            plaintext_violation_limit=2,
            plaintext_feedback=_PLAINTEXT_FEEDBACK,
        )
    )

    assert model_inputs[1][-1] == TextMessage(role="user", content=_PLAINTEXT_FEEDBACK)


def test_plaintext_is_not_checked_without_a_violation_limit() -> None:
    """Plaintext does not interfere with normal tool termination by default."""
    finish_executed = False

    async def generate_turn(
        _messages: tuple[ModelMessage, ...],
        _tools: tuple[Tool, ...],
    ) -> AssistantTurn:
        return AssistantTurn(
            text="Ordinary assistant output.",
            tool_calls=(ToolCall(call_id="finish", name="finish", arguments={}),),
        )

    async def finish(_arguments: Mapping[str, object]) -> ToolExecution:
        nonlocal finish_executed
        finish_executed = True
        return ToolExecution(output={"status": "finished"}, terminate=True)

    asyncio.run(
        run_agent(
            generate_turn=generate_turn,
            messages=(),
            tools=(_tool("finish", finish),),
        )
    )

    assert finish_executed


def test_plaintext_limit_requires_corrective_feedback() -> None:
    """A configured violation limit must have feedback for the model."""

    async def generate_turn(
        _messages: tuple[ModelMessage, ...],
        _tools: tuple[Tool, ...],
    ) -> AssistantTurn:
        return AssistantTurn()

    with pytest.raises(ValueError, match="Plaintext feedback is required"):
        asyncio.run(
            run_agent(
                generate_turn=generate_turn,
                messages=(),
                tools=(),
                plaintext_violation_limit=2,
            )
        )


def test_repeated_plaintext_raises_after_two_violations() -> None:
    """A model cannot retry the plaintext protocol indefinitely."""
    turns = 0

    async def generate_turn(
        _messages: tuple[ModelMessage, ...],
        _tools: tuple[Tool, ...],
    ) -> AssistantTurn:
        nonlocal turns
        turns += 1
        return AssistantTurn(text="Still plaintext.")

    with pytest.raises(
        PlaintextViolationLimitError,
        match="Agent emitted plaintext 2 times; the configured limit is 2",
    ):
        asyncio.run(
            run_agent(
                generate_turn=generate_turn,
                messages=(),
                tools=(),
                plaintext_violation_limit=2,
                plaintext_feedback=_PLAINTEXT_FEEDBACK,
            )
        )

    assert turns == 2


def test_agent_raises_after_thirty_two_unfinished_turns() -> None:
    """An agent cannot generate unfinished turns indefinitely."""
    turns = 0

    async def generate_turn(
        _messages: tuple[ModelMessage, ...],
        _tools: tuple[Tool, ...],
    ) -> AssistantTurn:
        nonlocal turns
        turns += 1
        return AssistantTurn(reasoning="Still working.")

    with pytest.raises(AgentTurnLimitError):
        asyncio.run(run_agent(generate_turn=generate_turn, messages=(), tools=()))

    assert turns == 32
