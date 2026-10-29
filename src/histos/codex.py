"""Codex integration that lets the model extend a Histos graph through tools."""

from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING, cast

from openai_codex.client import CodexClient, CodexConfig
from pydantic import BaseModel, Field, ValidationError

from histos.graph import AgentEntryKind, Entry, Graph, GraphError, GraphStore

if TYPE_CHECKING:
    from collections.abc import Callable

    from openai_codex.models import JsonObject, JsonValue

_TOOL_INPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "parent_id": {
            "type": "string",
            "description": "Exact ID of the entry that will parent the addition.",
        },
        "title": {"type": "string", "minLength": 1},
        "content": {"type": "string", "minLength": 1},
    },
    "required": ["parent_id", "title", "content"],
    "additionalProperties": False,
}

_DYNAMIC_TOOLS = cast(
    "list[JsonObject]",
    [
        {
            "type": "function",
            "name": "add_concept",
            "description": "Add an agent concept beneath any existing graph entry.",
            "inputSchema": _TOOL_INPUT_SCHEMA,
        },
        {
            "type": "function",
            "name": "ask_question",
            "description": "Add an agent question beneath any existing graph entry.",
            "inputSchema": _TOOL_INPUT_SCHEMA,
        },
    ],
)

_DEVELOPER_INSTRUCTIONS = """You extend a conversation represented as an ordered tree.
Use add_concept and ask_question to put every useful part of your response into the tree.
You may attach additions beneath any existing entry. Use exact entry IDs from the supplied graph.

Structure concepts hierarchically:
- Each concept must express one singular idea. Do not combine distinct ideas in one entry.
- Introduce a concise high-level concept beneath the entry it responds to.
- Put explanations, rationale, examples, consequences, and implementation details in separate
  sub-concepts beneath that high-level concept, using the entry ID returned by add_concept.
- If a sub-concept needs more detail, add another level beneath it rather than expanding it into
  a long multi-topic entry.
- Use sibling concepts for distinct ideas at the same level of abstraction.
- Give each concept a short title that names the idea. Keep its content focused on that title.
- Prefer a meaningful hierarchy over a flat list of concepts attached to the original question.

Do not edit or delete entries. Do not merely describe proposed additions in your final answer.
Do not inspect files, run commands, or use tools other than add_concept and ask_question.
Finish only after all useful response content has been written through graph tools.
"""


class CodexGraphError(RuntimeError):
    """Raised when Codex cannot produce graph additions."""


class _ToolArguments(BaseModel):
    parent_id: str
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)


class CodexGraphResponder:
    """Start a fresh Codex thread and expose graph-writing dynamic tools."""

    def __init__(self, store: GraphStore) -> None:
        """Configure a responder that mutates ``store`` through tool calls."""
        self._store = store
        self._respond_lock = threading.Lock()

    def respond(self) -> tuple[Entry, ...]:
        """Ask Codex to extend the current graph and return its additions."""
        with self._respond_lock:
            graph = self._store.read()
            if not graph.entries:
                msg = "Create a root question before asking Codex to respond"
                raise CodexGraphError(msg)

            additions: list[Entry] = []
            client = CodexClient(
                config=CodexConfig(
                    cwd=str(self._store.workspace),
                    client_name="histos",
                    client_title="Histos",
                ),
                approval_handler=self._tool_handler(additions),
            )
            try:
                client.start()
                client.initialize()
                thread_params: JsonObject = {
                    "approvalPolicy": "never",
                    "cwd": str(self._store.workspace),
                    "developerInstructions": _DEVELOPER_INSTRUCTIONS,
                    "dynamicTools": cast("JsonValue", _DYNAMIC_TOOLS),
                    "ephemeral": True,
                    "sandbox": "read-only",
                    "serviceName": "histos",
                }
                started_thread = client.thread_start(thread_params)
                prompt = _serialize_graph(graph)
                turn = client.turn_start(started_thread.thread.id, prompt)
                completed = client.wait_for_turn_completed(turn.turn.id)
                _ensure_completed(completed.turn.status.value)
            except CodexGraphError:
                raise
            except Exception as exc:
                msg = f"Codex response failed: {exc}"
                raise CodexGraphError(msg) from exc
            finally:
                client.close()

            if not additions:
                msg = "Codex completed without adding anything to the graph"
                raise CodexGraphError(msg)
            return tuple(additions)

    def _tool_handler(self, additions: list[Entry]) -> Callable[[str, JsonObject | None], JsonObject]:
        def handle(method: str, params: JsonObject | None) -> JsonObject:
            if method != "item/tool/call":
                return _deny_request(method)
            try:
                tool_params = _require_tool_params(params)
                kind = _tool_kind(tool_params.get("tool"))
                arguments = _parse_arguments(tool_params.get("arguments"))
                entry = self._store.add_agent_entry(
                    parent_id=arguments.parent_id,
                    kind=kind,
                    title=arguments.title,
                    content=arguments.content,
                )
                additions.append(entry)
                result = json.dumps({"entry_id": entry.id, "status": "added"})
            except (GraphError, ValidationError, ValueError, TypeError) as exc:
                return {
                    "contentItems": [{"type": "inputText", "text": str(exc)}],
                    "success": False,
                }
            else:
                return {
                    "contentItems": [{"type": "inputText", "text": result}],
                    "success": True,
                }

        return handle


def _ensure_completed(status: str) -> None:
    if status != "completed":
        msg = f"Codex turn ended with status {status}"
        raise CodexGraphError(msg)


def _require_tool_params(params: JsonObject | None) -> JsonObject:
    if params is None:
        msg = "Tool call has no parameters"
        raise GraphError(msg)
    return params


def _deny_request(method: str) -> JsonObject:
    if method == "item/commandExecution/requestApproval":
        return {"decision": "decline"}
    if method == "item/fileChange/requestApproval":
        return {"decision": "decline"}
    return {}


def _tool_kind(tool: object) -> AgentEntryKind:
    if tool == "add_concept":
        return "concept"
    if tool == "ask_question":
        return "question"
    msg = f"Unknown graph tool: {tool!r}"
    raise ValueError(msg)


def _parse_arguments(value: object) -> _ToolArguments:
    if isinstance(value, str):
        value = json.loads(value)
    return _ToolArguments.model_validate(value)


def _serialize_graph(graph: Graph) -> str:
    entries_by_parent: dict[str | None, list[Entry]] = {}
    for entry in graph.entries:
        entries_by_parent.setdefault(entry.parent_id, []).append(entry)

    lines = [
        "Respond to the complete conversation graph below by calling graph-writing tools.",
        "The ID shown on each entry is the exact parent_id to use.",
        "",
    ]

    def append_entry(entry: Entry, depth: int) -> None:
        heading = "#" * min(depth + 1, 6)
        lines.extend(
            [
                f"{heading} {entry.title}",
                f"{entry.author.title()} {entry.kind} · ID: {entry.id}",
                "",
                entry.content,
                "",
            ]
        )
        for child in entries_by_parent.get(entry.id, []):
            append_entry(child, depth + 1)

    roots = entries_by_parent.get(None, [])
    if len(roots) != 1:
        msg = "The graph must contain exactly one root"
        raise CodexGraphError(msg)
    append_entry(roots[0], 0)
    return "\n".join(lines)
