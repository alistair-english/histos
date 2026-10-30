"""Provider behavior for OpenAI Codex subscriptions."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import pytest

from histos.credentials import FileCredentialStore
from histos.model_providers import CodexProvider

if TYPE_CHECKING:
    from pathlib import Path

    from histos.model_provider import ModelProvider


def test_codex_provider_reuses_login_and_exposes_its_models(tmp_path: Path) -> None:
    """A configured provider does not repeat interactive login."""
    store = FileCredentialStore(tmp_path / "credentials.json")
    store.save(
        "openai-codex",
        {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_at": time.time() + 3600,
            "account_id": "account-id",
        },
    )
    provider: ModelProvider = CodexProvider(store)
    presented_urls: list[str] = []

    asyncio.run(provider.login(presented_urls.append))

    assert provider.id == "openai-codex"
    assert provider.get_models() == ["gpt-6.1-sol"]
    assert presented_urls == []
    assert callable(provider.generate_turn("gpt-6.1-sol"))


def test_codex_provider_rejects_an_unavailable_model(tmp_path: Path) -> None:
    """Model selection is checked before a provider request begins."""
    provider = CodexProvider(FileCredentialStore(tmp_path / "credentials.json"))

    with pytest.raises(ValueError, match="Model is not available from openai-codex"):
        provider.generate_turn("unknown-model")
