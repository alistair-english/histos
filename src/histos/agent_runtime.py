"""Run an ephemeral model and tool interaction loop."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

_PLAINTEXT_VIOLATION_LIMIT = 2
_AGENT_TURN_LIMIT = 32
_PLAINTEXT_ERROR = "Protocol error: plaintext is not visible to the user. Write all useful content through graph tools."


type JsonScalar = bool | int | float | str | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


@dataclass(frozen=True)
class TextMessage:
    """A system or user message supplied to a model."""

    role: Literal["system", "user"]
    content: str


@dataclass(frozen=True)
class ToolCall:
    """A model request to execute a named tool."""

    call_id: str
    name: str
    arguments: JsonObject


@dataclass(frozen=True)
class AssistantTurn:
    """One completed model turn."""

    tool_calls: tuple[ToolCall, ...] = ()
    text: str = ""
    reasoning: str = ""


@dataclass(frozen=True)
class ToolResultMessage:
    """The model-visible result of a tool call."""

    tool_call_id: str
    output: JsonValue
    is_error: bool = False


type ModelMessage = TextMessage | AssistantTurn | ToolResultMessage


@dataclass(frozen=True)
class ToolExecution:
    """A tool result plus runtime-only control metadata."""

    output: JsonValue
    is_error: bool = False
    terminate: bool = False


type ToolExecutor = Callable[[JsonObject], Awaitable[ToolExecution]]


@dataclass(frozen=True)
class Tool:
    """A model-visible definition paired with its executor."""

    name: str
    description: str
    input_schema: JsonObject
    execute: ToolExecutor


type GenerateTurn = Callable[
    [tuple[ModelMessage, ...], tuple[Tool, ...]],
    Awaitable[AssistantTurn],
]


class AgentRuntimeError(RuntimeError):
    """Base class for failures of an agent run."""


class PlaintextViolationLimitError(AgentRuntimeError):
    """Raised when a model repeatedly emits forbidden plaintext."""


class AgentTurnLimitError(AgentRuntimeError):
    """Raised when an agent run exceeds its model-turn limit."""


async def run_agent(
    *,
    generate_turn: GenerateTurn,
    messages: tuple[ModelMessage, ...],
    tools: tuple[Tool, ...],
) -> None:
    """Generate turns and execute tools until a tool requests termination."""
    transcript = list(messages)
    plaintext_violations = 0

    for _ in range(_AGENT_TURN_LIMIT):
        turn = await generate_turn(tuple(transcript), tools)
        transcript.append(turn)

        termination_requested = False
        for call in turn.tool_calls:
            tool = _find_tool(tools, call.name)
            if tool is None:
                execution = ToolExecution(
                    output={"error": f"Unknown tool: {call.name}"},
                    is_error=True,
                )
            else:
                execution = await tool.execute(call.arguments)

            transcript.append(
                ToolResultMessage(
                    tool_call_id=call.call_id,
                    output=execution.output,
                    is_error=execution.is_error,
                )
            )
            if execution.terminate:
                termination_requested = True
                break

        if turn.text.strip():
            plaintext_violations += 1
            if plaintext_violations >= _PLAINTEXT_VIOLATION_LIMIT:
                raise PlaintextViolationLimitError(_PLAINTEXT_ERROR)
            transcript.append(TextMessage(role="user", content=_PLAINTEXT_ERROR))
            continue

        if termination_requested:
            return

    msg = f"Agent exceeded the {_AGENT_TURN_LIMIT}-turn limit"
    raise AgentTurnLimitError(msg)


def _find_tool(tools: tuple[Tool, ...], name: str) -> Tool | None:
    """Find an executable tool by its model-visible name."""
    return next((tool for tool in tools if tool.name == name), None)
