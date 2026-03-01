"""Tests for TidalProvider."""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from song_shift.models import Playlist, Track
from song_shift.providers.tidal import TidalProvider


def _make_mock_track(
    id=123,
    name="Test Song",
    artist_name="Test Artist",
    album_name="Test Album",
    isrc="USRC12345678",
    duration=240,
):
    """Create a mock tidalapi Track."""
    track = MagicMock()
    track.id = id
    track.name = name
    track.artist.name = artist_name
    track.album.name = album_name
    track.isrc = isrc
    track.duration = duration
    return track


def _make_mock_playlist(
    id="abc-123-def",
    name="My Playlist",
    description="A test playlist",
    num_tracks=10,
):
    """Create a mock tidalapi Playlist."""
    playlist = MagicMock()
    playlist.id = id
    playlist.name = name
    playlist.description = description
    playlist.num_tracks = num_tracks
    return playlist


@pytest.fixture
def provider(credential_store):
    """Create a TidalProvider with mocked session."""
    with patch("song_shift.providers.tidal.tidalapi.Session") as mock_session_cls:
        p = TidalProvider(credential_store=credential_store)
        p._mock_session_cls = mock_session_cls
        yield p


class TestTidalAuthentication:
    def test_authenticate_starts_oauth_flow(self, provider):
        """authenticate() calls tidalapi login_oauth_simple."""
        provider._session.expiry_time = datetime.datetime(2026, 12, 31)
        provider._session.token_type = "Bearer"
        provider._session.access_token = "access_tok"
        provider._session.refresh_token = "refresh_tok"

        provider.authenticate()

        provider._session.login_oauth_simple.assert_called_once()

    def test_authenticate_stores_credentials(self, provider, credential_store):
        """After auth, credentials are saved to CredentialStore."""
        provider._session.token_type = "Bearer"
        provider._session.access_token = "access_tok"
        provider._session.refresh_token = "refresh_tok"
        provider._session.expiry_time = datetime.datetime(2026, 12, 31)

        provider.authenticate()

        creds = credential_store.get("tidal")
        assert creds is not None
        assert creds["token_type"] == "Bearer"
        assert creds["access_token"] == "access_tok"
        assert creds["refresh_token"] == "refresh_tok"
        assert creds["expiry_time"] is not None

    def test_is_authenticated_with_valid_token(self, provider, credential_store):
        """Returns True when stored token loads successfully."""
        credential_store.save(
            "tidal",
            {
                "token_type": "Bearer",
                "access_token": "access_tok",
                "refresh_token": "refresh_tok",
                "expiry_time": "2026-12-31T00:00:00",
            },
        )
        provider._session.check_login.return_value = False
        provider._session.load_oauth_session.return_value = True

        assert provider.is_authenticated() is True
        provider._session.load_oauth_session.assert_called_once_with(
            token_type="Bearer",
            access_token="access_tok",
            refresh_token="refresh_tok",
            expiry_time=datetime.datetime(2026, 12, 31),
        )

    def test_is_authenticated_without_credentials(self, provider):
        """Returns False when no credentials stored."""
        provider._session.check_login.return_value = False

        assert provider.is_authenticated() is False


class TestTidalPlaylists:
    def test_list_playlists_returns_mapped_playlists(self, provider):
        """Maps tidalapi Playlist objects to our Playlist model."""
        mock_playlist = _make_mock_playlist()
        provider._session.user.playlists.return_value = [mock_playlist]

        result = provider.list_playlists()

        assert len(result) == 1
        assert isinstance(result[0], Playlist)
        assert result[0].id == "abc-123-def"
        assert result[0].name == "My Playlist"
        assert result[0].description == "A test playlist"
        assert result[0].track_count == 10
        assert result[0].provider == "tidal"

    def test_get_playlist_tracks_returns_mapped_tracks(self, provider):
        """Maps tidalapi Track objects to our Track model with ISRC."""
        mock_track = _make_mock_track()
        mock_playlist = MagicMock()
        mock_playlist.tracks.return_value = [mock_track]
        provider._session.playlist.return_value = mock_playlist

        result = provider.get_playlist_tracks("abc-123-def")

        assert len(result) == 1
        assert isinstance(result[0], Track)
        assert result[0].title == "Test Song"
        assert result[0].artist == "Test Artist"
        assert result[0].album == "Test Album"
        assert result[0].isrc == "USRC12345678"
        assert result[0].duration_ms == 240_000
        assert result[0].provider_id == "123"
        assert result[0].provider == "tidal"


class TestTidalSearch:
    def test_search_track_by_isrc(self, provider):
        """Searches Tidal catalog by ISRC, returns mapped Track."""
        mock_track = _make_mock_track(isrc="USRC12345678")
        provider._session.search.return_value = {"tracks": [mock_track]}

        result = provider.search_track_by_isrc("USRC12345678")

        assert result is not None
        assert isinstance(result, Track)
        assert result.isrc == "USRC12345678"
        assert result.title == "Test Song"

    def test_search_track(self, provider):
        """Searches by query string, returns list of mapped Tracks."""
        mock_track = _make_mock_track()
        provider._session.search.return_value = {"tracks": [mock_track]}

        result = provider.search_track("Test Artist Test Song")

        assert len(result) == 1
        assert isinstance(result[0], Track)
        assert result[0].title == "Test Song"
        assert result[0].artist == "Test Artist"


class TestTidalPlaylistManagement:
    def test_create_playlist(self, provider):
        """Creates playlist via tidalapi, returns mapped Playlist."""
        mock_playlist = _make_mock_playlist(
            name="New Playlist", description="A new one", num_tracks=0
        )
        provider._session.user.create_playlist.return_value = mock_playlist

        result = provider.create_playlist("New Playlist", "A new one")

        assert isinstance(result, Playlist)
        assert result.name == "New Playlist"
        assert result.description == "A new one"
        assert result.track_count == 0
        assert result.provider == "tidal"
        provider._session.user.create_playlist.assert_called_once_with(
            "New Playlist", "A new one"
        )

    def test_add_tracks_to_playlist(self, provider):
        """Adds tracks by ID, returns count added."""
        mock_playlist = MagicMock()
        mock_playlist.add.return_value = [1, 2, 3]
        provider._session.playlist.return_value = mock_playlist

        result = provider.add_tracks_to_playlist(
            "abc-123-def", ["111", "222", "333"]
        )

        assert result == 3
        mock_playlist.add.assert_called_once_with(["111", "222", "333"])
