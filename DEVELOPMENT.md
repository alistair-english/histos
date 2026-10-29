# Development approach

Histos is developed from small, proven primitives. The goal is not to settle the whole architecture before implementation. The goal is to make one useful behavior clear, testable, and dependable before adding the next.

## The development loop

For each increment:

1. Name one observable behavior.
2. Write the smallest interface needed to express it.
3. Add a focused test for that behavior.
4. Implement only enough to make the test pass.
5. Run all checks.
6. Commit the completed behavior before starting another.

A good increment can be understood and reversed independently. If a change needs a broad design explanation or combines several behaviors, split it.

## Design rules

### Begin with behavior

Start from something Histos must do, not from a proposed layer, framework, or directory structure.

Prefer:

> An entry can be attached to an existing entry.

Over:

> Create the graph service and repository architecture.

### Introduce abstractions when code requires them

Do not create interfaces for hypothetical providers, stores, transports, or future implementations. Introduce a boundary when a concrete behavior has a concrete consumer and the boundary makes that code clearer.

A second implementation can justify generalising an existing interface. It does not need to be anticipated in the first implementation.

### Keep domain behavior independent

Core behavior should not depend on HTTP, UI frameworks, model SDKs, or storage formats unless that dependency is intrinsic to the behavior being implemented.

Adapters are added when the underlying behavior exists and needs to be exposed or persisted.

### Treat current decisions as revisable

Names, models, libraries, interfaces, and storage formats remain open to change. Tests should protect useful behavior rather than incidental implementation details.

### Prefer evidence from use

When the right design is unclear, build the smallest version that can produce evidence. Do not resolve uncertainty by adding speculative flexibility.

### Keep the active tree authoritative

Old implementations do not live in `_archive` directories. Git tags and worktrees preserve historical implementations without polluting searches, tests, packaging, or editor navigation.

The initial prototype is available at `prototype-v0` and in `../histos-prototype`. It can supply lessons and examples, but it does not define required behavior.

## Commit shape

Commit messages should name the behavior that became available:

```text
Add stable entry identifiers
Attach an entry to an existing parent
Reject attachment to an unknown parent
Persist entries in insertion order
```

Avoid broad commits such as:

```text
Build graph system
Add backend architecture
Refactor prototype
```

A commit is complete when:

- its behavior is covered by a focused test;
- all repository checks pass;
- unrelated cleanup and future scaffolding are absent;
- active documentation matches the behavior that actually exists.

## Choosing the next primitive

Choose the smallest behavior needed by the next real use case. Do not maintain a detailed speculative roadmap.

When several steps appear necessary, begin with the one that can be exercised without the others. For example, prove an in-memory conversation behavior before choosing its file format, HTTP representation, browser state model, or model-provider tool schema.

## Prototype recovery

Read an old file:

```bash
git show prototype-v0:src/histos/codex.py
```

Compare active work with the prototype:

```bash
git diff prototype-v0 -- src/histos/
```

Run or inspect the prototype from:

```text
../histos-prototype
```

Recover a specific lesson or behavior deliberately. Do not copy whole modules merely because they already exist.
