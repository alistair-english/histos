# Histos

Histos is an experiment in graph-based conversations with language models.

The project is being rebuilt from primitives. The active repository intentionally contains no application implementation yet. Its architecture will first be assembled piece by piece as typed, executable interface code. Concrete behavior will then be implemented against that skeleton one tested increment at a time.

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

## Checks

```bash
uv run pre-commit run --all-files
```
