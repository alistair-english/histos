"""Boundary behavior for global provider credential storage."""

import json
import stat
from pathlib import Path

from histos.credentials import FileCredentialStore


def test_file_store_keeps_provider_credentials_private_and_separate(tmp_path: Path) -> None:
    """Saving one provider preserves another provider in the private global file."""
    path = tmp_path / "histos" / "credentials.json"
    store = FileCredentialStore(path)

    store.save("first", {"secret": "one"})
    store.save("second", {"secret": "two"})

    assert store.load("first") == {"secret": "one"}
    assert store.load("second") == {"secret": "two"}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text()) == {
        "providers": {
            "first": {"secret": "one"},
            "second": {"secret": "two"},
        },
        "version": 1,
    }
