# Histos project context

> **Nothing in this document is a settled or rigid design.**
>
> This file records the ideas discussed so far so future agents do not have to reconstruct the conversation. Every architectural choice, library, interface, directory, and workflow remains open to revision. Treat all statements below as provisional context, not requirements or an approved specification.

## Product idea

Histos is an experimental local web interface for language models. Its central interaction model is intended to be a directed graph rather than a conventional linear chat context.

The current initial design treats the graph as the conversation itself and as the complete durable state supplied to a model. Pressing **Respond** starts a fresh model session from the whole current graph; provider conversations and separate turn histories are not retained. This is an initial direction for prototyping, not a permanent product constraint.

This is currently a personal/local project. Easy iteration matters more than polished cross-platform distribution.

## Current repository state

The repository currently contains project configuration only. There is no backend server, CLI, React application, graph engine, model integration, storage implementation, or OAuth implementation yet.

Current top-level shape:

```text
frontend/             React/TypeScript project configuration
src/histos/           Installable Python package
CONTEXT.md             This provisional handoff document
pyproject.toml         Python project and tool configuration
uv.lock                Locked Python dependencies
```

The frontend has Vite configuration and a Vite type declaration, but no application entry point or UI implementation.

## Provisional technology direction

The direction discussed so far is:

- Python 3.12 backend managed with `uv`.
- FastAPI served by Uvicorn.
- React and TypeScript frontend built with Vite.
- `@xyflow/react` for the graph UI.
- TanStack Query for remote/backend state.
- Zustand for transient UI state.
- Tailwind CSS for styling.
- HTTP plus server-sent events as an initial possibility for browser communication.

These choices are not final. Dependencies were added to establish a usable project baseline, not to lock the architecture.

### Current Python dependencies

The current runtime manifest is intentionally minimal and includes:

- FastAPI
- Typer
- Uvicorn

Provider HTTP/SSE clients, server-side SSE helpers, settings management, platform-directory helpers, and file-locking libraries should be added only when implemented code requires them. No model-provider SDK is installed.

## Local process architecture discussed

The leading idea was one backend process per canonical working directory, with multiple Histos sessions handled by that process.

Possible behavior discussed:

1. Running `histos` in a directory starts or reuses a backend scoped to that directory.
2. Each backend binds to `127.0.0.1` on an operating-system-assigned port.
3. The backend serves both the compiled frontend and API on the same origin in normal use.
4. Vite proxies API requests to Python during development.
5. Temporary process discovery information could live under `$XDG_RUNTIME_DIR` rather than in project state.
6. Duplicate processes for the same canonical directory could eventually be prevented with a lock and health check.

This was considered simpler and better isolated than a single global daemon. A global supervisor could still be introduced later if cross-workspace features become useful.

**None of this process behavior has been implemented or finalized.**

## Persistence preferences

The user would prefer workspace state to be plaintext and human-readable inside a `.histos/` directory in the working folder.

A database was initially suggested, but the preference is to avoid one if practical. The storage format, file layout, consistency strategy, locking, migrations, event logs, and Git behavior have not been designed.

Keep these conceptual boundaries in mind:

- `.histos/` would contain persistent workspace/session/graph state.
- Global user configuration would live outside the workspace, likely under an XDG config location.
- Runtime PID, port, lock, and authentication-token information should not be treated as persistent workspace state.
- Provider secrets and OAuth refresh tokens should not be placed in `.histos/`.

These are preferences and discussion outcomes, not a finalized storage contract.

## Backend and distribution context

Python was chosen as the current backend direction because the user is stronger in Python and `uv` distribution is sufficient for this personal project.

The possible future route to Electron was discussed. One possible Electron architecture would start a packaged Python process and load its localhost URL. Packaging Python as an Electron sidecar would add per-platform build and signing work, but this is not a current goal.

Serving the built React application from FastAPI would avoid CORS in normal use. Localhost alone does not remove CORS: different ports are still different origins. During development, Vite is expected to proxy backend routes.

No Electron work or packaging work should be started without revisiting the need.

## Model-provider direction

Histos must not depend on Pi. Pi and the local `pi-claude-oauth-adapter` repository were inspected only as references for the complexity of subscription OAuth and provider-specific request behavior.

The immediate provider focus is expected to be an OpenAI Codex subscription. Anthropic subscription support may come later.

Multi-model support should be considered from the beginning, but this should not trigger a large abstraction framework before the first provider works.

Ideas discussed include keeping the following concerns separable:

- credential acquisition and refresh;
- provider/account policy;
- wire protocol encoding and decoding;
- HTTP/SSE/WebSocket transport;
- normalized model requests and streamed model events.

The Codex implementation should be native to Histos rather than importing Pi. The exact interfaces, OAuth flow, credential format, transport abstraction, and event vocabulary are not settled.

OAuth credentials would probably be global rather than workspace-specific. Because the proposed process model allows multiple workspace processes, token refresh may eventually require a shared cross-process lock and atomic credential updates. This has not been implemented.

## Initial graph design

The current graph direction is documented in
[`docs/initial-graph-design.md`](docs/initial-graph-design.md).

> **These are initial design choices for a prototype.** They are not settled
> requirements or a permanent graph contract. Challenge and change them when
> implementation experience or real model interactions suggest a better design.

The current working choices are:

- The initial “graph” is an ordered, rooted tree with one parent per entry and
  any number of children.
- The root is a user question.
- Parent edges are deliberately untyped. Their meaning is inferred from entry
  kinds and content rather than formally defined.
- Authorship and entry kind are separate properties. The initial combinations
  are user question, user message, agent concept, agent question, and agent
  tool call.
- The graph is editable current state rather than an immutable audit log,
  although full editing is outside the first prototype.
- A model receives the whole current tree whenever the user presses **Respond**.
  There is no focus entry, attention/change prompt, persisted turn transcript,
  or continued provider conversation.
- Each response uses a fresh model session. Anything needed by a later response
  must be represented in the graph.
- The agent may initially add concepts, questions, and tool calls anywhere in
  the tree, but may not edit or delete existing entries.
- Tool calls are parented graph entries; concepts based on their results may be
  attached beneath them.
- Model input should be lightweight readable prose with enough stable references
  to address parents, not a verbose database-like node dump.
- The leading output approach is provider-native graph-writing tools rather than
  requiring the model to print raw JSON.

Serialization order, stable-reference format, exact graph-writing operations,
tool-result representation, and many other details remain unresolved. Depth-
first and breadth-first prompt order both remain candidates. Avoid creating
elaborate graph/model abstractions until concrete behavior requires them.

## Source layout

The current Python package lives under `src/histos/` instead of a top-level `backend/` or `cli/` directory.

The reasoning was that Histos may eventually contain a CLI, server, graph logic, model drivers, and storage code within one installable Python package. Possible future subpackages were mentioned, but none have been created:

```text
src/histos/
├── cli/
├── server/
├── graph/
├── models/
└── storage/
```

This layout is also provisional. Do not create these directories until code requires them.

The frontend is directly under `frontend/`. An earlier `apps/web/` workspace layout was rejected as unnecessary nesting for the current project size. npm workspaces are not in use.

## Development tooling

Install dependencies with:

```bash
uv sync
npm install --prefix frontend
uv run pre-commit install
```

Run all configured checks manually with:

```bash
uv run pre-commit run --all-files
```

The pre-commit hook currently runs six checks on every commit:

1. Ruff formatting for staged Python files.
2. Ruff linting across the project.
3. Strict Pyright checking for `src/`.
4. Prettier formatting for staged supported frontend/configuration files.
5. Strict TypeScript checking.
6. ESLint with type-aware TypeScript, React Hooks, and React Refresh rules.

If Ruff or Prettier modifies files, the commit is aborted. Stage the formatted files and commit again.

### Ruff policy

Ruff enables all stable rules and uses an explicit exclusion list. Existing exclusions are limited to formatter conflicts, mutually exclusive docstring rules, and per-file copyright headers:

- `COM812`
- `ISC001`
- `D203`
- `D213`
- `CPY001`

The intention is to start strict and add exclusions only when a concrete rule is unsuitable.

### Formatting

Python formatting:

```bash
uv run ruff format .
```

Frontend and project-file formatting:

```bash
npm exec --prefix frontend -- prettier --write .
```

Generated lockfiles are excluded from Prettier.

## Suggested immediate next milestone

The next milestone discussed was the smallest possible backend lifecycle slice:

1. Add a `histos` CLI entry point.
2. Resolve the canonical current working directory.
3. Start FastAPI on `127.0.0.1` using an available port.
4. Print the local URL.
5. Add a minimal health endpoint reporting the workspace.
6. Shut down cleanly on Ctrl-C.

This would validate packaging, CLI startup, loopback binding, dynamic ports, and workspace scoping before adding persistence, sessions, models, OAuth, or graph behavior.

This milestone is a suggestion, not a committed plan. Reassess it before implementation.

## Guidance for future agents

- Keep changes small and testable.
- Do not infer settled requirements from exploratory discussion.
- Do not introduce a database without revisiting the plaintext `.histos/` preference.
- Do not add Pi as a runtime or build dependency.
- Do not over-design graph or model abstractions before concrete behavior exists.
- Preserve the possibility of multiple providers even if Codex is implemented first.
- Keep secrets out of workspace state.
- Prefer a working vertical slice over speculative framework code.
- Update this document when discussion materially changes direction, but continue to label unsettled ideas as provisional.
