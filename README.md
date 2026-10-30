# Histos

Histos is an experiment in graph-based conversations with language models.

The project is being rebuilt from primitives as small, tested functional increments. The active implementation includes the conversation graph, ephemeral agent runtime, graph-response composition, Codex authentication, and a native Codex model-turn adapter.

See [`DEVELOPMENT.md`](DEVELOPMENT.md) for the working method.

## Prototype reference

The initial end-to-end prototype is preserved in two places:

- Git tag: `prototype-v0`
- Local reference worktree: `../histos-prototype`

Inspect a prototype file without restoring it:

```bash
git show prototype-v0:src/histos/graph.py
```

The prototype is reference material, not the specification for the rebuild.

## Setup

Requirements:

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

```bash
uv sync
uv run pre-commit install
```

## Codex login

Sign in with the ChatGPT account that has your Codex subscription:

```bash
uv run histos login
```

Credentials are stored globally in `$XDG_CONFIG_HOME/histos/credentials.json`, or `~/.config/histos/credentials.json` when `XDG_CONFIG_HOME` is unset. The file is created with user-only permissions and is never stored in conversation state.

## Checks

```bash
uv run pre-commit run --all-files
```
