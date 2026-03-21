"""Tests for ShazamProvider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from song_shift.models import Playlist, Track
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


class TestShazamCSVParsing:
    def test_list_playlists_returns_single_synthetic_playlist(
        self, provider, credential_store, tmp_path
    ):
        """Returns one Playlist with id='shazam-library' and correct track_count."""
        csv_file = _write_csv(
            tmp_path / "shazams.csv",
            rows=[("Song A", "Artist A", "100"), ("Song B", "Artist B", "200")],
        )
        credential_store.save("shazam", {"csv_path": str(csv_file)})

        playlists = provider.list_playlists()

        assert len(playlists) == 1
        assert isinstance(playlists[0], Playlist)
        assert playlists[0].id == "shazam-library"
        assert playlists[0].name == "My Shazam Tracks"
        assert playlists[0].track_count == 2
        assert playlists[0].provider == "shazam"

    def test_get_playlist_tracks_parses_csv(
        self, provider, credential_store, tmp_path
    ):
        """Parses CSV rows into Track objects with correct field mapping."""
        csv_file = _write_csv(
            tmp_path / "shazams.csv",
            rows=[("Bohemian Rhapsody", "Queen", "456")],
        )
        credential_store.save("shazam", {"csv_path": str(csv_file)})

        tracks = provider.get_playlist_tracks("shazam-library")

        assert len(tracks) == 1
        assert isinstance(tracks[0], Track)
        assert tracks[0].title == "Bohemian Rhapsody"
        assert tracks[0].artist == "Queen"
        assert tracks[0].provider_id == "456"

    def test_get_playlist_tracks_skips_empty_rows(
        self, provider, credential_store, tmp_path
    ):
        """Rows with empty Title AND Artist are skipped."""
        csv_file = _write_csv(
            tmp_path / "shazams.csv",
            rows=[
                ("Song A", "Artist A", "100"),
                ("", "", "999"),
                ("Song B", "Artist B", "200"),
            ],
        )
        credential_store.save("shazam", {"csv_path": str(csv_file)})

        tracks = provider.get_playlist_tracks("shazam-library")

        assert len(tracks) == 2
        assert tracks[0].title == "Song A"
        assert tracks[1].title == "Song B"

    def test_get_playlist_tracks_handles_missing_fields(
        self, provider, credential_store, tmp_path
    ):
        """Gracefully handles rows with missing optional columns."""
        csv_file = _write_csv(
            tmp_path / "shazams.csv",
            headers=("Title", "Artist"),
            rows=[("Song A", "Artist A")],
        )
        credential_store.save("shazam", {"csv_path": str(csv_file)})

        tracks = provider.get_playlist_tracks("shazam-library")

        assert len(tracks) == 1
        assert tracks[0].title == "Song A"
        assert tracks[0].provider_id == ""

    def test_get_playlist_tracks_sets_provider_fields(
        self, provider, credential_store, tmp_path
    ):
        """provider='shazam', album='', isrc=None, duration_ms=None."""
        csv_file = _write_csv(
            tmp_path / "shazams.csv",
            rows=[("Song A", "Artist A", "100")],
        )
        credential_store.save("shazam", {"csv_path": str(csv_file)})

        tracks = provider.get_playlist_tracks("shazam-library")

        assert tracks[0].provider == "shazam"
        assert tracks[0].album == ""
        assert tracks[0].isrc is None
        assert tracks[0].duration_ms is None


def _make_shazam_hit(title="Test Song", subtitle="Test Artist", key="12345"):
    """Create a mock shazamio search hit dict."""
    return {
        "heading": {"title": title, "subtitle": subtitle},
        "key": key,
    }


class TestShazamSearch:
    def test_search_track_returns_mapped_results(self, provider):
        """search_track() calls shazamio and maps results to Track objects."""
        mock_result = {
            "tracks": {
                "hits": [
                    _make_shazam_hit("Bohemian Rhapsody", "Queen", "456"),
                    _make_shazam_hit("We Will Rock You", "Queen", "789"),
                ]
            }
        }

        mock_shazam = MagicMock()
        mock_shazam.search_track = AsyncMock(return_value=mock_result)

        with patch("song_shift.providers.shazam.Shazam", return_value=mock_shazam):
            tracks = provider.search_track("Queen")

        assert len(tracks) == 2
        assert isinstance(tracks[0], Track)
        assert tracks[0].title == "Bohemian Rhapsody"
        assert tracks[0].artist == "Queen"
        assert tracks[0].provider_id == "456"
        assert tracks[0].provider == "shazam"
        assert tracks[1].title == "We Will Rock You"
        assert tracks[1].provider_id == "789"

    def test_search_track_empty_results(self, provider):
        """Returns empty list when no matches."""
        mock_result = {"tracks": {"hits": []}}

        mock_shazam = MagicMock()
        mock_shazam.search_track = AsyncMock(return_value=mock_result)

        with patch("song_shift.providers.shazam.Shazam", return_value=mock_shazam):
            tracks = provider.search_track("nonexistent song xyz")

        assert tracks == []

    def test_search_track_by_isrc_returns_none(self, provider):
        """Always returns None (not supported)."""
        assert provider.search_track_by_isrc("USAT29900609") is None


class TestShazamReadOnly:
    def test_create_playlist_raises_not_implemented(self, provider):
        """Raises NotImplementedError with descriptive message."""
        with pytest.raises(NotImplementedError, match="read-only source"):
            provider.create_playlist("My Playlist", "Description")

    def test_add_tracks_raises_not_implemented(self, provider):
        """Raises NotImplementedError with descriptive message."""
        with pytest.raises(NotImplementedError, match="read-only source"):
            provider.add_tracks_to_playlist("playlist-id", ["track1", "track2"])
