"""Tests for ShazamProvider."""

from unittest.mock import patch

import pytest

from song_shift.providers.shazam import ShazamProvider


def _write_csv(path, headers=("Title", "Artist", "TrackKey"), rows=()):
    """Write a CSV file with given headers and rows."""
    with open(path, "w", newline="") as f:
        f.write(",".join(headers) + "\n")
        for row in rows:
            f.write(",".join(row) + "\n")
    return path


@pytest.fixture
def provider(credential_store):
    """Create a ShazamProvider with a test credential store."""
    return ShazamProvider(credential_store=credential_store)


class TestShazamAuthentication:
    def test_authenticate_prompts_for_csv_path(self, provider, credential_store, tmp_path):
        """authenticate() with valid CSV path stores it in credentials."""
        csv_file = _write_csv(tmp_path / "shazams.csv", rows=[("Song", "Artist", "123")])

        with patch("builtins.input", return_value=str(csv_file)):
            provider.authenticate()

        creds = credential_store.get("shazam")
        assert creds is not None
        assert creds["csv_path"] == str(csv_file)

    def test_authenticate_rejects_missing_file(self, provider):
        """authenticate() raises FileNotFoundError for non-existent path."""
        with patch("builtins.input", return_value="/nonexistent/file.csv"):
            with pytest.raises(FileNotFoundError):
                provider.authenticate()

    def test_authenticate_rejects_invalid_csv(self, provider, tmp_path):
        """authenticate() raises ValueError for CSV without required headers."""
        csv_file = _write_csv(tmp_path / "bad.csv", headers=("Foo", "Bar"))

        with patch("builtins.input", return_value=str(csv_file)):
            with pytest.raises(ValueError, match="CSV missing required headers"):
                provider.authenticate()

    def test_is_authenticated_true_when_file_exists(self, provider, credential_store, tmp_path):
        """Returns True when credential has valid file path."""
        csv_file = _write_csv(tmp_path / "shazams.csv")
        credential_store.save("shazam", {"csv_path": str(csv_file)})

        assert provider.is_authenticated() is True

    def test_is_authenticated_false_when_no_credentials(self, provider):
        """Returns False when no credentials stored."""
        assert provider.is_authenticated() is False

    def test_is_authenticated_false_when_file_deleted(self, provider, credential_store, tmp_path):
        """Returns False when stored path no longer exists."""
        csv_file = tmp_path / "shazams.csv"
        _write_csv(csv_file)
        credential_store.save("shazam", {"csv_path": str(csv_file)})
        csv_file.unlink()

        assert provider.is_authenticated() is False
