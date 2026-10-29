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

## Project checks

All checks run automatically before each commit. Run them manually with:

```bash
uv run pre-commit run --all-files
```
