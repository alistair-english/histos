# Initial graph design

> **This is an initial, deliberately incomplete design.**
>
> It exists to give the first prototype a coherent direction, not to establish a
> permanent graph model or protocol. Every choice here may be challenged or
> changed after using the prototype. In particular, the project should prefer
> evidence from real interactions over preserving this document.

## Purpose

Histos treats a graph as the conversation itself, rather than as a view over a
separate linear chat history. The graph is the durable state that a model reads
and extends.

Pressing **Respond** starts a fresh model session against the current graph. A
provider conversation or turn transcript is not retained between responses.
Anything that should affect a later response must therefore be represented in
the graph.

## Initial shape

Although Histos uses graph terminology, the initial structure is an ordered,
rooted tree:

- The root is a user question.
- Every other entry has exactly one parent.
- A parent may have any number of children.
- Sibling order is significant and stable.
- Multiple parents, cross-links, and multiple roots are deferred.

This restriction is only an initial simplification. It should not prevent later
experiments with a more general directed graph.

## Parent relationships

The parent-to-child edge is intentionally untyped. Its exact meaning is inferred
from the connected entries and their content. Depending on context, a child may
continue, explain, decompose, answer, support, or otherwise follow from its
parent.

The prototype does not need to formally define or validate those meanings. Edge
types such as `answers`, `supports`, or `decomposes` should only be introduced if
real usage demonstrates that they are useful.

## Entry authors and kinds

Authorship and kind are separate properties, even though the UI may display
combined labels such as “Agent concept.” The initially valid combinations are:

| Author | Kind        | Intended use                          |
| ------ | ----------- | ------------------------------------- |
| User   | `question`  | The root question or a later request  |
| User   | `message`   | Context, feedback, or an answer       |
| Agent  | `concept`   | An explanation or idea                |
| Agent  | `question`  | A question requiring user input       |
| Agent  | `tool_call` | A recorded tool invocation and result |

This set is provisional. Separating author from kind leaves room to add useful
combinations later without redesigning identity or rendering.

Larger agent responses should normally be decomposed into concept children when
those sub-concepts are independently useful. This is guidance for the agent,
not a structural validation rule.

## Tool calls

A tool call is an agent-authored entry and must have a parent. It may contain
kind-specific information such as the tool name, arguments, execution status,
and result. A concept derived from the result can be attached beneath the tool
call, preserving the causal chain:

```text
Agent concept
└── Agent tool call
    └── Agent concept based on the result
```

The exact tool-call schema and the treatment of large results remain open.

## User and agent capabilities

The intended product is an editable graph representing current conversation
state, not an immutable audit log. The user should eventually be able to edit,
move, reorder, and remove existing entries. Those editing capabilities are not
required for the first prototype.

User edit history is not model context. After an edit, a model receives the
current graph without being told what changed or whether an entry was edited.

The initial agent interface is deliberately stricter:

- The agent may add agent-authored concepts, questions, and tool calls.
- It may attach additions anywhere in the supplied tree.
- It may not edit, move, or delete existing entries.
- It may not create user-authored entries.
- It may not create another root.

These permissions are initial safety and simplicity choices, not permanent
constraints.

## Respond behavior

The initial interaction is intentionally simple:

1. The user creates or extends the graph.
2. The user presses **Respond**.
3. Histos serializes the entire current tree.
4. A fresh model session receives that serialization.
5. The agent adds entries to the graph.
6. The provider session and temporary turn transcript are discarded.

There is no selected focus entry, persisted turn history, provider conversation
continuation, or “changed since last response” attention prompt. The agent may
respond anywhere in the tree.

A temporary provider transcript may still be needed within one response so the
model can receive tool results. It is not part of the durable conversation.

## Model input

The model should receive a lightweight, readable representation of the whole
tree rather than a database-like dump. It needs enough information to identify
entries and understand their parent relationships, but repeated “node” labels
and redundant child lists are unnecessary.

A possible representation is:

```markdown
# How should authentication work?

User question · @authentication

I need sessions to survive server restarts.

## Authentication approach

Agent concept · @authentication-approach  
Replying to @authentication

Use short-lived access tokens with persistent refresh tokens.

### Browser persistence

Agent question · @browser-persistence  
Replying to @authentication-approach

Should login survive closing the browser?
```

Because the agent may attach an entry anywhere, entries need stable,
unambiguous references. Human-readable generated handles are an initial
candidate because they may be easier for models and people to use than opaque
references such as `[q1]`. Titles should not have to be globally unique or act
as durable identity. The exact identity and handle scheme is not settled.

The serialization order is also unsettled:

- Depth-first order keeps each branch coherent.
- Breadth-first order places deeper parts of the tree later, which may make the
  frontier more prominent to a model.

The first implementation may choose the simplest deterministic ordering and
change it after testing real graph prompts. Prompt ordering is not part of the
persistent graph contract.

## Model output

The agent should not be required to print raw JSON as its prose response. The
leading option is a small provider-native graph-writing tool interface, for
example operations to add a concept or ask a question beneath a referenced
parent. The backend can validate those structured calls while the agent writes
ordinary prose.

Graph-writing operations are control operations and do not themselves need to
appear as visible tool-call entries. Actual working tool invocations do appear
in the graph.

The exact operation names, schemas, validation behavior, and fallback for models
without tool calling are deliberately unresolved.

## Initial prototype boundary

The smallest useful graph-behavior prototype needs to demonstrate:

1. Creating a root user question.
2. Attaching new user entries to existing entries.
3. Displaying the ordered tree as a directed graph.
4. Pressing **Respond** to invoke a fresh model session with the whole tree.
5. Applying agent additions at arbitrary valid parent locations.
6. Representing agent tool calls as parented graph entries when tool support is
   introduced.

Full graph editing is not required even though user editability is part of the
product direction.

## Explicitly deferred

The following should remain open until experience justifies a choice:

- Multiple parents, cross-links, and multiple roots.
- Typed or otherwise formal edge semantics.
- Context selection, pruning, summarization, and token-limit handling.
- Final serialization order and formatting.
- Final identity and model-facing handle format.
- Exact graph-writing tool schemas.
- Editing, reparenting, deletion, undo, and version history.
- Retry and regeneration behavior.
- Concurrent users, edits, or agent invocations.
- Streaming versus batched application of agent additions.
- Question resolution state.
- Storage and truncation of large tool results.

Deferral is intentional. None of these omissions should be interpreted as a
decision that the feature is unnecessary.
