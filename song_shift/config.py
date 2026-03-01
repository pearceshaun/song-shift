"""Credential storage for music service providers."""

import json
import os
import stat
from pathlib import Path


class CredentialStore:
    """Persist and retrieve provider credentials.

    Stores JSON in ~/.config/song-shift/credentials.json (or path
    specified by SONG_SHIFT_CONFIG_DIR env var). File permissions
    are set to 0o600 (owner read/write only).
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        if config_dir is not None:
            self._config_dir = config_dir
        else:
            env_dir = os.environ.get("SONG_SHIFT_CONFIG_DIR")
            if env_dir:
                self._config_dir = Path(env_dir)
            else:
                self._config_dir = Path.home() / ".config" / "song-shift"
        self._credentials_path = self._config_dir / "credentials.json"

    def _read(self) -> dict:
        if not self._credentials_path.exists():
            return {}
        with open(self._credentials_path) as f:
            return json.load(f)

    def _write(self, data: dict) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with open(self._credentials_path, "w") as f:
            json.dump(data, f, indent=2)
        self._credentials_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    def get(self, provider: str) -> dict | None:
        """Get credentials for a provider, or None if not found."""
        data = self._read()
        return data.get(provider)

    def save(self, provider: str, credentials: dict) -> None:
        """Save credentials for a provider."""
        data = self._read()
        data[provider] = credentials
        self._write(data)

    def delete(self, provider: str) -> None:
        """Delete credentials for a provider."""
        data = self._read()
        data.pop(provider, None)
        self._write(data)

    def list_providers(self) -> list[str]:
        """Return names of providers with saved credentials."""
        data = self._read()
        return list(data.keys())
