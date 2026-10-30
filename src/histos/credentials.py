"""Store provider credentials outside conversation state."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import Mapping


type CredentialValue = bool | int | float | str | list[CredentialValue] | dict[str, CredentialValue] | None
type ProviderCredentials = dict[str, CredentialValue]


class CredentialStore(Protocol):
    """Persistence required by a model provider's authentication implementation."""

    def load(self, provider: str) -> ProviderCredentials | None:
        """Load one provider's credentials, if present."""
        ...

    def save(self, provider: str, credentials: Mapping[str, CredentialValue]) -> None:
        """Atomically replace one provider's credentials."""
        ...


class FileCredentialStore:
    """Store provider credentials in a private global JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        """Use an explicit path or Histos's global configuration directory."""
        self._path = path or _default_credentials_path()

    @property
    def path(self) -> Path:
        """Return the credentials file path."""
        return self._path

    def load(self, provider: str) -> ProviderCredentials | None:
        """Load one provider's credentials, if present."""
        document = self._read_document()
        providers = document.get("providers")
        if not isinstance(providers, dict):
            return None
        credentials = providers.get(provider)
        if not isinstance(credentials, dict):
            return None
        return cast("ProviderCredentials", credentials)

    def save(self, provider: str, credentials: Mapping[str, CredentialValue]) -> None:
        """Atomically replace one provider's credentials with private permissions."""
        document = self._read_document()
        providers = document.get("providers")
        if not isinstance(providers, dict):
            providers = {}
        providers[provider] = dict(credentials)
        document = {"version": 1, "providers": providers}

        self._path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary_path = self._path.with_name(f".{self._path.name}.{os.getpid()}.tmp")
        descriptor = os.open(temporary_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                json.dump(document, file, indent=2, sort_keys=True)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            temporary_path.replace(self._path)
            self._path.chmod(0o600)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _read_document(self) -> dict[str, CredentialValue]:
        if not self._path.exists():
            return {"version": 1, "providers": {}}
        try:
            value = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            msg = f"Cannot read credentials from {self._path}: {error}"
            raise CredentialStoreError(msg) from error
        if not isinstance(value, dict):
            msg = f"Credentials file must contain a JSON object: {self._path}"
            raise CredentialStoreError(msg)
        return cast("dict[str, CredentialValue]", value)


class CredentialStoreError(RuntimeError):
    """Raised when global provider credentials cannot be read or written."""


def _default_credentials_path() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(config_home) if config_home else Path.home() / ".config"
    return base / "histos" / "credentials.json"
