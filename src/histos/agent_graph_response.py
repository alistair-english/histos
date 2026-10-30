"""Compose the generic agent runtime with Histos graph-writing behavior."""

from __future__ import annotations

from histos.agent_graph_writing import add_agent_entry
from histos.agent_runtime import (
    AgentRuntimeError,
    GenerateTurn,
    JsonObject,
    TextMessage,
    Tool,
    ToolExecution,
    ToolExecutor,
    run_agent,
)
from histos.graph import ConversationGraph, EntryKind, EntryReference
from histos.model_graph_projection import MODEL_GRAPH_FORMAT, project_graph_for_model

_PLAINTEXT_FEEDBACK = (
    "Protocol error: plaintext is not visible to the user. Write all useful content through graph tools."
)
_SYSTEM_INSTRUCTIONS = f"""\
You respond to a conversation graph by extending it with graph-writing tools.
Write every useful part of your response through add_concept or ask_question.
Use finish_response only after all useful content has been added.
Do not edit or delete existing entries.

{MODEL_GRAPH_FORMAT}"""

_GRAPH_TOOL_SCHEMA: JsonObject = {
    "type": "object",
    "properties": {
        "parent": {"type": "string", "minLength": 1},
        "reference": {"type": "string", "minLength": 1},
        "content": {"type": "string", "minLength": 1},
        "label": {"type": "string", "minLength": 1},
    },
    "required": ["parent", "reference", "content"],
    "additionalProperties": False,
}
_FINISH_TOOL_SCHEMA: JsonObject = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


async def respond_to_graph(
    graph: ConversationGraph,
    *,
    generate_turn: GenerateTurn,
) -> tuple[ConversationGraph, str | None]:
    """Run an agent response and retain graph additions after expected failures."""
    if not graph.snapshot().entries:
        msg = "A graph must have a root question before an agent can respond"
        raise ValueError(msg)

    working_graph = graph

    def graph_writer(kind: EntryKind) -> ToolExecutor:
        async def execute(arguments: JsonObject) -> ToolExecution:
            nonlocal working_graph
            try:
                parent = EntryReference(_required_string(arguments, "parent"))
                reference = EntryReference(_required_string(arguments, "reference"))
                content = _required_string(arguments, "content")
                label = _optional_string(arguments, "label")
                working_graph, entry = add_agent_entry(
                    working_graph,
                    parent=parent,
                    reference=reference,
                    kind=kind,
                    content=content,
                    label=label,
                )
            except (TypeError, ValueError) as error:
                return ToolExecution(output={"error": str(error)}, is_error=True)

            return ToolExecution(
                output={
                    "status": "added",
                    "reference": entry.reference.value,
                    "parent": parent.value,
                }
            )

        return execute

    async def finish_response(_arguments: JsonObject) -> ToolExecution:
        return ToolExecution(output={"status": "finished"}, terminate=True)

    tools = (
        Tool(
            name="add_concept",
            description="Add an agent concept beneath an existing graph entry.",
            input_schema=_GRAPH_TOOL_SCHEMA,
            execute=graph_writer(EntryKind.CONCEPT),
        ),
        Tool(
            name="ask_question",
            description="Add an agent question beneath an existing graph entry.",
            input_schema=_GRAPH_TOOL_SCHEMA,
            execute=graph_writer(EntryKind.QUESTION),
        ),
        Tool(
            name="finish_response",
            description="Finish after all useful response content has been added to the graph.",
            input_schema=_FINISH_TOOL_SCHEMA,
            execute=finish_response,
        ),
    )
    messages = (
        TextMessage(role="system", content=_SYSTEM_INSTRUCTIONS),
        TextMessage(
            role="user",
            content=(f"Respond to the complete conversation graph below.\n\n{project_graph_for_model(graph)}"),
        ),
    )

    try:
        await run_agent(
            generate_turn=generate_turn,
            messages=messages,
            tools=tools,
            plaintext_violation_limit=2,
            plaintext_feedback=_PLAINTEXT_FEEDBACK,
        )
    except AgentRuntimeError as error:
        return working_graph, str(error)

    return working_graph, None


def _required_string(arguments: JsonObject, name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str):
        msg = f"Tool argument '{name}' must be a string"
        raise TypeError(msg)
    return value


def _optional_string(arguments: JsonObject, name: str) -> str | None:
    if name not in arguments:
        return None
    return _required_string(arguments, name)
