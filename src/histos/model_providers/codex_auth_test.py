"""Boundary behavior for Codex authentication."""

import asyncio
import base64
import json
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from histos.credentials import FileCredentialStore
from histos.model_providers.codex_auth import (
    CodexAuthenticationError,
    codex_access_token,
    codex_authorization_url,
    parse_codex_callback,
)


def test_authorization_request_and_callback_are_bound_by_state() -> None:
    """The browser callback must return the state sent in the PKCE authorization request."""
    authorization_url = codex_authorization_url(verifier="verifier", state="expected-state")
    query = parse_qs(urlparse(authorization_url).query)

    assert query["response_type"] == ["code"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"] == ["expected-state"]
    assert query["redirect_uri"] == ["http://localhost:1455/auth/callback"]
    assert parse_codex_callback(
        "GET /auth/callback?code=accepted&state=expected-state HTTP/1.1",
        expected_state="expected-state",
    ) == ("accepted", None)
    assert parse_codex_callback(
        "GET /auth/callback?code=rejected&state=other-state HTTP/1.1",
        expected_state="expected-state",
    ) == (None, "OAuth state did not match")


def test_access_token_uses_logged_in_default_account(tmp_path: Path) -> None:
    """A valid saved login supplies the token needed by a Codex model adapter."""
    store = FileCredentialStore(tmp_path / "credentials.json")
    store.save(
        "openai-codex",
        {
            "access_token": _access_token("account-123"),
            "refresh_token": "refresh-token",
            "expires_at": time.time() + 3600,
            "account_id": "account-123",
        },
    )

    token = asyncio.run(codex_access_token(store=store))

    assert token == _access_token("account-123")


def test_access_token_requires_login(tmp_path: Path) -> None:
    """Generation cannot silently continue without a configured Codex account."""
    store = FileCredentialStore(tmp_path / "credentials.json")

    with pytest.raises(CodexAuthenticationError, match="run `histos login` first"):
        asyncio.run(codex_access_token(store=store))


def _access_token(account_id: str) -> str:
    payload = {"https://api.openai.com/auth": {"chatgpt_account_id": account_id}}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"header.{encoded}.signature"
