"""Histos command-line entry point."""

from __future__ import annotations

import argparse
import asyncio
import sys
import webbrowser
from typing import TYPE_CHECKING

from histos.credentials import FileCredentialStore
from histos.model_providers import CodexProvider
from histos.model_providers.codex_auth import CodexAuthenticationError

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(arguments: Sequence[str] | None = None) -> None:
    """Run a Histos command."""
    parser = argparse.ArgumentParser(prog="histos")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("login", help="Log in to an OpenAI Codex subscription")
    parsed = parser.parse_args(arguments)

    if parsed.command == "login":
        provider = CodexProvider(FileCredentialStore())
        try:
            asyncio.run(provider.login(_present_authorization_url))
        except CodexAuthenticationError as error:
            parser.exit(1, f"Codex login failed: {error}\n")
        sys.stdout.write("Codex login complete.\n")


def _present_authorization_url(url: str) -> None:
    sys.stdout.write(f"Open this URL to log in to Codex:\n\n{url}\n")
    webbrowser.open(url)
