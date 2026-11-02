"""Histos command-line entry point."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
import webbrowser
from threading import Thread
from typing import TYPE_CHECKING

import uvicorn

from histos.credentials import FileCredentialStore
from histos.model_providers import CodexProvider
from histos.model_providers.codex_auth import CodexAuthenticationError

if TYPE_CHECKING:
    from collections.abc import Sequence


_LOCAL_URL = "http://127.0.0.1:8000"


def _serve() -> None:
    config = uvicorn.Config("histos.server:app", host="127.0.0.1", port=8000)
    server = uvicorn.Server(config)
    Thread(target=_open_browser_when_ready, args=(server,), daemon=True).start()
    server.run()


def _open_browser_when_ready(server: uvicorn.Server) -> None:
    while not server.started and not server.should_exit:
        time.sleep(0.05)
    if server.started:
        webbrowser.open(_LOCAL_URL)


def main(arguments: Sequence[str] | None = None) -> None:
    """Run a Histos command."""
    parser = argparse.ArgumentParser(prog="histos")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("login", help="Log in to an OpenAI Codex subscription")
    parsed = parser.parse_args(arguments)

    if parsed.command is None:
        _serve()
    elif parsed.command == "login":
        provider = CodexProvider(FileCredentialStore())
        try:
            asyncio.run(provider.login(_present_authorization_url))
        except CodexAuthenticationError as error:
            parser.exit(1, f"Codex login failed: {error}\n")
        sys.stdout.write("Codex login complete.\n")


def _present_authorization_url(url: str) -> None:
    sys.stdout.write(f"Open this URL to log in to Codex:\n\n{url}\n")
    webbrowser.open(url)
