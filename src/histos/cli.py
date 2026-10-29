"""Command-line entry points for Histos."""

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from openai_codex import Codex

from histos.server import create_app

app = typer.Typer(no_args_is_help=True)
_DEFAULT_WORKSPACE = Path.cwd()


@app.command()
def serve(
    workspace: Annotated[
        Path,
        typer.Option(
            "--workspace",
            "-w",
            help="Workspace whose .histos directory will hold the graph.",
        ),
    ] = _DEFAULT_WORKSPACE,
    host: Annotated[str, typer.Option(help="Interface to bind.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port to bind.")] = 8000,
) -> None:
    """Run the local Histos API and built frontend."""
    canonical_workspace = workspace.resolve()
    typer.echo(f"Histos workspace: {canonical_workspace}")
    typer.echo(f"Open http://{host}:{port}")
    uvicorn.run(create_app(canonical_workspace), host=host, port=port)


@app.command()
def login() -> None:
    """Sign the bundled Codex runtime into a ChatGPT subscription."""
    with Codex() as codex:
        handle = codex.login_chatgpt()
        typer.echo("Opening ChatGPT sign-in in your browser...")
        typer.echo(handle.auth_url)
        webbrowser.open(handle.auth_url)
        completion = handle.wait()
        if not completion.success:
            raise typer.Exit(code=1)
        typer.echo("Codex login complete.")
