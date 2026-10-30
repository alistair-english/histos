"""Shared contract implemented by model provider plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from histos.agent_runtime import GenerateTurn
    from histos.credentials import CredentialStore


class ModelProvider(ABC):
    """Authentication, models, and generation supplied by one provider."""

    @abstractmethod
    def __init__(self, credential_store: CredentialStore) -> None:
        """Construct the provider with centralized credential storage."""
        ...

    @property
    @abstractmethod
    def id(self) -> str:
        """Return the provider's stable identifier."""
        ...

    @abstractmethod
    async def login(self, present_url: Callable[[str], None]) -> None:
        """Ensure the provider has valid credentials, logging in when absent."""
        ...

    @abstractmethod
    def get_models(self) -> list[str]:
        """Return model identifiers available through this provider."""
        ...

    @abstractmethod
    def generate_turn(self, model: str) -> GenerateTurn:
        """Create a normalized turn generator for one provider model."""
        ...
