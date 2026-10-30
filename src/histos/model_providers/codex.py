"""OpenAI Codex subscription model provider."""

from __future__ import annotations

from typing import TYPE_CHECKING

from histos.model_provider import ModelProvider
from histos.model_providers.codex_auth import CodexNotLoggedInError, authorize_codex, login_codex
from histos.model_providers.codex_model import create_codex_generate_turn

if TYPE_CHECKING:
    from collections.abc import Callable

    from histos.agent_runtime import GenerateTurn
    from histos.credentials import CredentialStore

_MODELS = ("gpt-6.1-sol",)


class CodexProvider(ModelProvider):
    """Authenticate and generate turns through a ChatGPT Codex subscription."""

    def __init__(self, credential_store: CredentialStore) -> None:
        """Use centralized storage for this provider's OAuth credentials."""
        self._credential_store = credential_store

    @property
    def id(self) -> str:
        """Return the stable Codex provider identifier."""
        return "openai-codex"

    async def login(self, present_url: Callable[[str], None]) -> None:
        """Reuse valid credentials or start browser login when none exist."""
        try:
            await authorize_codex(store=self._credential_store)
        except CodexNotLoggedInError:
            await login_codex(
                present_authorization_url=present_url,
                store=self._credential_store,
            )

    def get_models(self) -> list[str]:
        """Return the Codex models currently exposed by Histos."""
        return list(_MODELS)

    def generate_turn(self, model: str) -> GenerateTurn:
        """Create a normalized turn generator for a supported Codex model."""
        if model not in _MODELS:
            msg = f"Model is not available from {self.id}: {model}"
            raise ValueError(msg)
        return create_codex_generate_turn(
            model=model,
            credential_store=self._credential_store,
        )
