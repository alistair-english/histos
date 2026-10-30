"""Generate normalized model turns with an OpenAI Codex subscription."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from histos.agent_runtime import (
    AssistantTurn,
    GenerateTurn,
    JsonObject,
    JsonValue,
    ModelGenerationError,
    ModelMessage,
    TextMessage,
    Tool,
    ToolCall,
)
from histos.model_providers.codex_auth import CodexAuthenticationError, authorize_codex

if TYPE_CHECKING:
    from collections.abc import Iterable

    from histos.credentials import CredentialStore
    from histos.model_providers.codex_auth import CodexAuthorization

_CODEX_RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"


def create_codex_generate_turn(
    *,
    model: str,
    credential_store: CredentialStore | None = None,
) -> GenerateTurn:
    """Create the normalized turn generator for one Codex model."""

    async def generate_turn(
        messages: tuple[ModelMessage, ...],
        tools: tuple[Tool, ...],
    ) -> AssistantTurn:
        try:
            authorization = await authorize_codex(store=credential_store)
            request_body = encode_codex_request(messages=messages, tools=tools, model=model)
            return await asyncio.to_thread(_request_codex_turn, request_body, authorization)
        except ModelGenerationError:
            raise
        except CodexAuthenticationError as error:
            raise ModelGenerationError(str(error)) from error

    return generate_turn


def encode_codex_request(
    *,
    messages: tuple[ModelMessage, ...],
    tools: tuple[Tool, ...],
    model: str,
) -> JsonObject:
    """Translate the normalized runtime transcript into a Codex Responses request."""
    instructions: list[str] = []
    inputs: list[JsonValue] = []

    for index, message in enumerate(messages):
        if isinstance(message, TextMessage):
            if message.role == "system":
                instructions.append(message.content)
            else:
                inputs.append(
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": message.content}],
                    }
                )
        elif isinstance(message, AssistantTurn):
            if message.text:
                inputs.append(
                    {
                        "type": "message",
                        "id": f"msg_histos_{index}",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": message.text,
                                "annotations": [],
                            }
                        ],
                    }
                )
            inputs.extend(_encode_tool_call(call) for call in message.tool_calls)
        else:
            inputs.append(
                {
                    "type": "function_call_output",
                    "call_id": message.tool_call_id,
                    "output": json.dumps(message.output, separators=(",", ":")),
                }
            )

    request: JsonObject = {
        "model": model,
        "store": False,
        "stream": True,
        "instructions": "\n\n".join(instructions) or "You are a helpful assistant.",
        "input": inputs,
        "text": {"verbosity": "low"},
        "include": ["reasoning.encrypted_content"],
        "tool_choice": "auto",
        "parallel_tool_calls": True,
    }
    if tools:
        encoded_tools: list[JsonValue] = [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
                "strict": False,
            }
            for tool in tools
        ]
        request["tools"] = encoded_tools
    return request


def decode_codex_events(events: Iterable[JsonObject]) -> AssistantTurn:
    """Translate one completed Codex SSE event sequence into a normalized turn."""
    text_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    completed = False

    for event in events:
        event_type = event.get("type")
        if event_type == "response.output_text.delta":
            _append_string(event, "delta", text_parts)
        elif event_type == "response.reasoning_summary_text.delta":
            _append_string(event, "delta", reasoning_parts)
        elif event_type == "response.output_item.done":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "function_call":
                tool_calls.append(_decode_tool_call(cast("dict[str, object]", item)))
        elif event_type == "response.completed":
            completed = True
        elif event_type in ("error", "response.failed", "response.incomplete"):
            raise ModelGenerationError(_event_error(event))

    if not completed:
        msg = "Codex response stream ended without a completed response"
        raise ModelGenerationError(msg)
    return AssistantTurn(
        tool_calls=tuple(tool_calls),
        text="".join(text_parts),
        reasoning="".join(reasoning_parts),
    )


def _encode_tool_call(call: ToolCall) -> JsonObject:
    return {
        "type": "function_call",
        "call_id": call.call_id,
        "name": call.name,
        "arguments": json.dumps(call.arguments, separators=(",", ":")),
    }


def _decode_tool_call(item: dict[str, object]) -> ToolCall:
    call_id = item.get("call_id")
    name = item.get("name")
    arguments_json = item.get("arguments")
    if not isinstance(call_id, str) or not isinstance(name, str) or not isinstance(arguments_json, str):
        msg = "Codex returned an invalid function call"
        raise ModelGenerationError(msg)
    try:
        arguments: object = json.loads(arguments_json)
    except json.JSONDecodeError as error:
        msg = f"Codex returned invalid arguments for tool {name}: {error}"
        raise ModelGenerationError(msg) from error
    if not isinstance(arguments, dict):
        msg = f"Codex returned non-object arguments for tool {name}"
        raise ModelGenerationError(msg)
    return ToolCall(call_id=call_id, name=name, arguments=cast("JsonObject", arguments))


def _append_string(event: JsonObject, name: str, destination: list[str]) -> None:
    value = event.get(name)
    if isinstance(value, str):
        destination.append(value)


def _event_error(event: JsonObject) -> str:
    error = event.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str):
            return message
    response = event.get("response")
    if isinstance(response, dict):
        response_error = response.get("error")
        if isinstance(response_error, dict):
            message = response_error.get("message")
            if isinstance(message, str):
                return message
    return f"Codex generation failed with event: {event.get('type')}"


def _request_codex_turn(body: JsonObject, authorization: CodexAuthorization) -> AssistantTurn:
    request = Request(
        _CODEX_RESPONSES_URL,
        data=json.dumps(body, separators=(",", ":")).encode(),
        headers={
            "Authorization": f"Bearer {authorization.access_token}",
            "chatgpt-account-id": authorization.account_id,
            "originator": "histos",
            "User-Agent": "histos/0.1.0",
            "OpenAI-Beta": "responses=experimental",
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:  # noqa: S310 - fixed Codex HTTPS endpoint
            return decode_codex_events(_read_sse_events(response))
    except HTTPError as error:
        detail = error.read().decode(errors="replace")
        msg = f"Codex request failed ({error.code}): {detail}"
        raise ModelGenerationError(msg) from error
    except (OSError, URLError) as error:
        msg = f"Codex request failed: {error}"
        raise ModelGenerationError(msg) from error


def _read_sse_events(lines: Iterable[bytes]) -> Iterable[JsonObject]:
    data_lines: list[str] = []
    for raw_line in lines:
        line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
        if not line:
            event = _decode_sse_data(data_lines)
            data_lines = []
            if event is not None:
                yield event
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    event = _decode_sse_data(data_lines)
    if event is not None:
        yield event


def _decode_sse_data(data_lines: list[str]) -> JsonObject | None:
    if not data_lines:
        return None
    data = "\n".join(data_lines)
    if data == "[DONE]":
        return None
    try:
        value: object = json.loads(data)
    except json.JSONDecodeError as error:
        msg = f"Codex returned invalid SSE data: {error}"
        raise ModelGenerationError(msg) from error
    if not isinstance(value, dict):
        msg = "Codex returned a non-object SSE event"
        raise ModelGenerationError(msg)
    return cast("JsonObject", value)
