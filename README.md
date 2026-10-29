# Histos

A local, graph-based interface for language models.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 22
- npm 10

## Setup

```bash
uv sync
npm install --prefix frontend
```

## Project checks

```bash
uv run ruff check .
uv run pyright
npm run check --prefix frontend
npm run lint --prefix frontend
```
