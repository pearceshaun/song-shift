import stat

import pytest

from song_shift.config import CredentialStore


class TestCredentialStore:
    def test_save_and_get_credentials(self, tmp_path):
        store = CredentialStore(config_dir=tmp_path)
        creds = {"access_token": "abc123", "refresh_token": "def456"}
        store.save("tidal", creds)
        assert store.get("tidal") == creds

    def test_get_nonexistent_provider(self, tmp_path):
        store = CredentialStore(config_dir=tmp_path)
        assert store.get("spotify") is None

    def test_delete_credentials(self, tmp_path):
        store = CredentialStore(config_dir=tmp_path)
        store.save("tidal", {"token": "abc"})
        store.delete("tidal")
        assert store.get("tidal") is None

    def test_list_providers(self, tmp_path):
        store = CredentialStore(config_dir=tmp_path)
        store.save("tidal", {"token": "abc"})
        store.save("apple_music", {"token": "xyz"})
        providers = store.list_providers()
        assert sorted(providers) == ["apple_music", "tidal"]

    def test_creates_config_directory(self, tmp_path):
        config_dir = tmp_path / "nested" / "config"
        store = CredentialStore(config_dir=config_dir)
        store.save("tidal", {"token": "abc"})
        assert config_dir.exists()
        assert config_dir.is_dir()

    def test_credentials_file_permissions(self, tmp_path):
        store = CredentialStore(config_dir=tmp_path)
        store.save("tidal", {"token": "abc"})
        creds_path = tmp_path / "credentials.json"
        mode = creds_path.stat().st_mode
        assert mode & stat.S_IRWXG == 0, "Group should have no permissions"
        assert mode & stat.S_IRWXO == 0, "Others should have no permissions"
        assert mode & stat.S_IRUSR, "Owner should have read permission"
        assert mode & stat.S_IWUSR, "Owner should have write permission"
