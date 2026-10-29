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
uv run pre-commit install
```

## Run the prototype

Sign in with the ChatGPT account that has your Codex subscription:

```bash
uv run histos login
```

For development, run the API and frontend in separate terminals:

```bash
uv run histos serve
npm run --prefix frontend dev
```

Open <http://127.0.0.1:5173>. Graph state is stored in `.histos/graph.json`.

To run the built single-server version:

```bash
npm run --prefix frontend build
uv run histos serve
```

Open <http://127.0.0.1:8000>.

## Project checks

All checks run automatically before each commit. Run them manually with:

```bash
uv run pre-commit run --all-files
```

Ruff and Prettier format staged files during commits. If they change a file, stage the result and commit again.

Format manually with:

```bash
uv run ruff format .
npm exec --prefix frontend -- prettier --write .
```
