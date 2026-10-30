"""Authenticate the OpenAI Codex subscription provider."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import json
import secrets
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from histos.credentials import CredentialStore, FileCredentialStore, ProviderCredentials

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

_PROVIDER_ID = "openai-codex"
_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
_AUTHORIZATION_URL = "https://auth.openai.com/oauth/authorize"
_TOKEN_URL = "https://auth.openai.com/oauth/token"  # noqa: S105 - URL, not a credential
_REDIRECT_URI = "http://localhost:1455/auth/callback"
_SCOPE = "openid profile email offline_access"
_ACCOUNT_CLAIM = "https://api.openai.com/auth"
_CALLBACK_TIMEOUT_SECONDS = 15 * 60
_REFRESH_MARGIN_SECONDS = 60
_HTTP_REQUEST_LINE_PARTS = 2
_JWT_PARTS = 3


class CodexAuthenticationError(RuntimeError):
    """Raised when Codex login or credential refresh fails."""


class CodexNotLoggedInError(CodexAuthenticationError):
    """Raised when no Codex credentials have been stored."""


@dataclass(frozen=True)
class CodexAuthorization:
    """Current authorization needed by the Codex model transport."""

    access_token: str
    account_id: str


@dataclass(frozen=True)
class CodexCredentials:
    """OAuth credentials managed internally by the Codex provider integration."""

    access_token: str
    refresh_token: str
    expires_at: float
    account_id: str


async def login_codex(
    *,
    present_authorization_url: Callable[[str], None],
    store: CredentialStore | None = None,
) -> None:
    """Complete browser OAuth and save credentials for the default Codex account."""
    credential_store = store or FileCredentialStore()
    verifier = _pkce_verifier()
    state = secrets.token_urlsafe(24)
    authorization_url = codex_authorization_url(verifier=verifier, state=state)
    callback = asyncio.get_running_loop().create_future()

    async def receive_callback(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = (await reader.readline()).decode("ascii", errors="replace").strip()
            while await reader.readline() not in (b"\r\n", b"\n", b""):
                pass
            code, error = parse_codex_callback(request_line, expected_state=state)
            if error is not None:
                await _send_callback_page(writer, status="400 Bad Request", message=error)
                if not callback.done():
                    callback.set_exception(CodexAuthenticationError(error))
                return
            await _send_callback_page(
                writer,
                status="200 OK",
                message="OpenAI authentication completed. You can close this window.",
            )
            if not callback.done() and code is not None:
                callback.set_result(code)
        except Exception as error:  # noqa: BLE001 - callback errors must reach the waiting login operation
            if not callback.done():
                callback.set_exception(error)
        finally:
            writer.close()
            await writer.wait_closed()

    try:
        server = await asyncio.start_server(receive_callback, host="127.0.0.1", port=1455)
    except OSError as error:
        msg = "Cannot start the Codex login callback server on 127.0.0.1:1455"
        raise CodexAuthenticationError(msg) from error

    async with server:
        present_authorization_url(authorization_url)
        try:
            code = await asyncio.wait_for(callback, timeout=_CALLBACK_TIMEOUT_SECONDS)
        except TimeoutError as error:
            msg = "Codex login timed out waiting for the browser callback"
            raise CodexAuthenticationError(msg) from error

    credentials = await asyncio.to_thread(_exchange_authorization_code, code, verifier)
    credential_store.save(_PROVIDER_ID, _serialize_credentials(credentials))


async def authorize_codex(*, store: CredentialStore | None = None) -> CodexAuthorization:
    """Return current Codex authorization, refreshing and saving it when needed."""
    credential_store = store or FileCredentialStore()
    credentials = _load_credentials(credential_store)
    if credentials.expires_at <= time.time() + _REFRESH_MARGIN_SECONDS:
        credentials = await asyncio.to_thread(_refresh_credentials, credentials.refresh_token)
        credential_store.save(_PROVIDER_ID, _serialize_credentials(credentials))
    return CodexAuthorization(
        access_token=credentials.access_token,
        account_id=credentials.account_id,
    )


async def codex_access_token(*, store: CredentialStore | None = None) -> str:
    """Return a valid access token for callers that do not need account metadata."""
    return (await authorize_codex(store=store)).access_token


def _load_credentials(store: CredentialStore) -> CodexCredentials:
    stored = store.load(_PROVIDER_ID)
    if stored is None:
        msg = "Codex is not logged in; run `histos login` first"
        raise CodexNotLoggedInError(msg)
    try:
        access_token = _required_string(stored, "access_token")
        refresh_token = _required_string(stored, "refresh_token")
        expires_at = _required_number(stored, "expires_at")
        account_id = _required_string(stored, "account_id")
    except (TypeError, ValueError) as error:
        msg = "Stored Codex credentials are invalid; run `histos login` again"
        raise CodexAuthenticationError(msg) from error
    return CodexCredentials(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        account_id=account_id,
    )


def _pkce_verifier() -> str:
    return secrets.token_urlsafe(64)


def codex_authorization_url(*, verifier: str, state: str) -> str:
    """Build the Codex PKCE authorization URL for a login attempt."""
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    query = urlencode(
        {
            "response_type": "code",
            "client_id": _CLIENT_ID,
            "redirect_uri": _REDIRECT_URI,
            "scope": _SCOPE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
            "originator": "histos",
        }
    )
    return f"{_AUTHORIZATION_URL}?{query}"


def parse_codex_callback(request_line: str, *, expected_state: str) -> tuple[str | None, str | None]:
    """Validate a Codex browser callback and extract its authorization code."""
    parts = request_line.split()
    if len(parts) < _HTTP_REQUEST_LINE_PARTS:
        return None, "Invalid OAuth callback request"
    url = urlparse(parts[1])
    if url.path != "/auth/callback":
        return None, "OAuth callback route not found"
    query = parse_qs(url.query)
    if query.get("state", [None])[0] != expected_state:
        return None, "OAuth state did not match"
    provider_error = query.get("error_description", query.get("error", [None]))[0]
    if provider_error is not None:
        return None, f"OpenAI rejected login: {provider_error}"
    code = query.get("code", [None])[0]
    if code is None:
        return None, "OAuth callback did not contain an authorization code"
    return code, None


async def _send_callback_page(
    writer: asyncio.StreamWriter,
    *,
    status: str,
    message: str,
) -> None:
    safe_message = html.escape(message)
    body = f"<!doctype html><html><body><p>{safe_message}</p></body></html>".encode()
    headers = (
        f"HTTP/1.1 {status}\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode()
    writer.write(headers + body)
    await writer.drain()


def _exchange_authorization_code(code: str, verifier: str) -> CodexCredentials:
    return _request_token(
        {
            "grant_type": "authorization_code",
            "client_id": _CLIENT_ID,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": _REDIRECT_URI,
        },
        operation="exchange",
    )


def _refresh_credentials(refresh_token: str) -> CodexCredentials:
    return _request_token(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": _CLIENT_ID,
        },
        operation="refresh",
    )


def _request_token(form: Mapping[str, str], *, operation: str) -> CodexCredentials:
    request = Request(
        _TOKEN_URL,
        data=urlencode(form).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed HTTPS endpoint
            payload: object = json.load(response)
    except HTTPError as error:
        detail = error.read().decode(errors="replace")
        msg = f"Codex token {operation} failed ({error.code}): {detail}"
        raise CodexAuthenticationError(msg) from error
    except (OSError, URLError, json.JSONDecodeError) as error:
        msg = f"Codex token {operation} failed: {error}"
        raise CodexAuthenticationError(msg) from error

    if not isinstance(payload, dict):
        msg = f"Codex token {operation} returned an invalid response"
        raise CodexAuthenticationError(msg)
    token = cast("dict[str, object]", payload)
    try:
        access_token = _required_string(token, "access_token")
        refresh_token = _required_string(token, "refresh_token")
        expires_in = _required_number(token, "expires_in")
        account_id = _account_id(access_token)
    except (TypeError, ValueError) as error:
        msg = f"Codex token {operation} response is missing required fields"
        raise CodexAuthenticationError(msg) from error
    return CodexCredentials(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=time.time() + expires_in,
        account_id=account_id,
    )


def _account_id(access_token: str) -> str:
    parts = access_token.split(".")
    if len(parts) != _JWT_PARTS:
        msg = "Codex access token is not a JWT"
        raise ValueError(msg)
    encoded = parts[1] + "=" * (-len(parts[1]) % 4)
    payload = json.loads(base64.urlsafe_b64decode(encoded))
    if not isinstance(payload, dict):
        msg = "Codex access token has an invalid payload"
        raise TypeError(msg)
    token_payload = cast("dict[str, object]", payload)
    auth = token_payload.get(_ACCOUNT_CLAIM)
    if not isinstance(auth, dict):
        msg = "Codex access token has no account claim"
        raise TypeError(msg)
    account_claim = cast("dict[str, object]", auth)
    account_id = account_claim.get("chatgpt_account_id")
    if not isinstance(account_id, str) or not account_id:
        msg = "Codex access token has no account ID"
        raise ValueError(msg)
    return account_id


def _serialize_credentials(credentials: CodexCredentials) -> ProviderCredentials:
    return {
        "access_token": credentials.access_token,
        "refresh_token": credentials.refresh_token,
        "expires_at": credentials.expires_at,
        "account_id": credentials.account_id,
    }


def _required_string(values: Mapping[str, object], name: str) -> str:
    value = values.get(name)
    if not isinstance(value, str) or not value:
        msg = f"{name} must be a non-empty string"
        raise TypeError(msg)
    return value


def _required_number(values: Mapping[str, object], name: str) -> float:
    value = values.get(name)
    if not isinstance(value, int | float):
        msg = f"{name} must be a number"
        raise TypeError(msg)
    return float(value)
