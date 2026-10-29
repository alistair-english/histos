# Development approach

Histos is rebuilt from the prototype as an architecture expressed in code. The architecture is assembled as a sequence of small, reviewable, functional increments rather than designed completely in prose or as a behaviorless skeleton.

## Governing rule: minimum functionality, deliberate structure

**Add only the minimum functionality or features currently being explored, while using each addition to discover and establish the right architecture and extension points.**

Write as little code as possible, but do not reduce line count by coupling responsibilities or baking a provisional product choice into an unrelated boundary. Conversely, do not add abstractions, extension points, or layers merely because they may become useful later.

Each increment must balance both sides of the rule:

- it delivers the smallest usable or constructible piece of the feature under discussion;
- it makes the responsibilities and boundaries exercised by that piece explicit;
- it accommodates known, credible extension directions where doing so affects the current shape;
- it does not implement deferred features or generic flexibility;
- it is allowed to revise an earlier structure when working code provides better evidence.

The target is not the fewest possible lines in isolation. It is the least code that provides current value without creating an avoidable structural dead end.

## Current phase: graph foundation

Build the graph structure one functional piece at a time. Use that work to make the domain architecture visible before adding persistence, model providers, HTTP, or UI concerns.

For each increment:

1. Name the smallest functionality or feature being added.
2. Identify the domain concepts and architectural boundaries that feature actually exercises.
3. Add only the types and interfaces needed to express those concepts and boundaries.
4. Implement the minimum useful behavior required by the feature.
5. Add focused committed tests at the code boundaries or seams whose behavior needs to be pinned; use temporary tests or scripts for checks within those boundaries.
6. Run all checks and commit before starting another feature.

An increment should leave code that can be used or constructed, navigated, type-checked, and changed. It may contain immutable value types, protocols, request and result types, dependency declarations, and small concrete domain behavior. It should not contain placeholder algorithms disguised as implementation.

## What the architecture should show

As functional increments accumulate, the code should make these things apparent without requiring an architecture document:

- the core domain vocabulary and invariants;
- which operations the application supports;
- which dependencies those operations require;
- where persistence, model providers, and delivery mechanisms meet the application;
- which data crosses each boundary;
- how the application is assembled from implementations of those boundaries.

Use the prototype to discover these relationships. Preserve its lessons, not necessarily its modules, names, or coupled interfaces.

## Define boundaries with functionality

Interfaces are introduced with the functionality that needs them, not extracted only after concrete classes have coupled concerns and not speculated into existence ahead of use.

Define boundaries incrementally rather than attempting to describe the whole system in a single change. A later increment may revise an earlier interface when working code makes a better boundary visible.

Prefer interfaces owned by the code that uses them. Keep provider SDKs, HTTP frameworks, filesystem formats, and UI libraries outside the domain and application contracts.

An interface is justified when the current functionality needs it to do at least one of the following:

- express a domain operation;
- mark an architectural boundary;
- describe data crossing that boundary;
- connect existing pieces without coupling their responsibilities;
- make a dependency direction visible and checkable.

Do not add generic extension points that reveal nothing about Histos.

## Keep architecture in code

Prose records the development method and short rationale only. The source tree is the authoritative architecture model.

Prefer:

```python
class GraphRepository(Protocol):
    def load(self) -> ConversationGraph: ...
    def save(self, graph: ConversationGraph) -> None: ...
```

Over a document saying:

> The application will probably use a repository abstraction for graph storage.

Use names, signatures, modules, dependency direction, and composition code to communicate the design. Use tests to demonstrate relationships that the type system cannot express directly.

## Architecture code rules

Architecture-focused code may use:

- immutable domain value types;
- enums, tagged unions, and type aliases;
- `Protocol` or abstract interfaces;
- application command and query signatures;
- boundary-specific request, response, and event types;
- dependency containers or composition function signatures;
- exceptions that are part of a public contract;
- `...` in interface bodies where Python requires a body.

Architecture-focused code should not use:

- fake return values such as empty graphs or hard-coded responses;
- `pass` or `NotImplementedError` in classes presented as usable implementations;
- framework decorators merely to make the architecture look complete;
- filesystem, network, provider, or process behavior;
- compatibility layers copied wholesale from the prototype.

If a component cannot do useful work yet, represent it as an interface rather than a pretend implementation.

## Testing boundaries and seams

Committed tests pin functionality and behavior at code boundaries and seams. They verify the contracts between responsibilities without coupling the suite to implementation details within those boundaries.

Do not commit tests aimed only at behavior internal to a boundary. When building new code, create ad hoc temporary tests or scripts to check that the implementation works as expected, then remove them before completing the increment.

Committed tests must run quickly so the complete suite can run on every commit. A slow test belongs outside the pre-commit suite unless its boundary can be exercised through a faster substitute.

Place committed tests beside their implementation using the `*_test.py` suffix. Test modules are development code and must be excluded from built distributions.

Useful committed architecture tests include:

- public types import from their intended modules;
- a small in-test implementation satisfies a protocol at a boundary;
- an application operation exposes its required dependencies and result type;
- composition connects inward-facing interfaces without importing adapters into the core;
- observable behavior crossing a boundary remains stable.

Architecture-focused tests should be narrow and removed when stronger boundary behavior tests supersede them. Strict type checking remains part of the test suite. An increment is incomplete if its architectural relationships exist only by convention.

## Adding implementations

Implement from domain primitives outward, but only as far as the current feature requires:

1. Name one observable behavior.
2. Define or refine the contract exercised by that behavior.
3. Write a focused committed test when the behavior crosses a boundary or seam; otherwise create a temporary test or script.
4. Implement only enough to satisfy that check.
5. Run all checks.
6. Commit the completed behavior.

Implement domain behavior before infrastructure where dependency order permits. Add filesystem, provider, HTTP, CLI, and UI adapters only when a current feature needs them, against inward-facing contracts rather than allowing those technologies to reshape the core implicitly.

The architecture remains editable throughout. When implementation disproves an interface, change the contract deliberately and update every affected connection in the same change.

## Using the prototype

The initial prototype is available at `prototype-v0` and in `../histos-prototype`.

For each functional area:

1. Read the corresponding prototype path end to end.
2. Identify responsibilities, dependencies, and data crossing boundaries.
3. Re-express only the findings needed by the current feature as types, interfaces, and minimal behavior.
4. Leave unrelated implementation details in the prototype.

Read an old file:

```bash
git show prototype-v0:src/histos/codex.py
```

Compare active work with the prototype:

```bash
git diff prototype-v0 -- src/histos/
```

The prototype is evidence about the system, not a template to copy. In particular, a prototype class that mixes domain rules, persistence, locking, and ID generation should become several explicit contracts when those responsibilities belong on different sides of the architecture.

## Commit shape

Commit messages should name the small capability or structural fact that became available:

```text
Define conversation graph value types
Create a root user question
Define graph persistence boundary
Reject attachment to an unknown parent
Persist graph entries atomically
```

Avoid broad commits such as:

```text
Design backend architecture
Build graph system
Refactor prototype
```

A commit is complete when:

- the current functionality is usable or constructible;
- its behavior or architectural relationship is tested;
- all repository checks pass;
- unrelated features, abstractions, and cleanup are absent;
- the active contracts describe the implementation.

## Active tree

The active source tree is authoritative. Old implementations do not live in `_archive` directories. Git tags and worktrees preserve historical implementations without polluting searches, tests, packaging, or editor navigation.
