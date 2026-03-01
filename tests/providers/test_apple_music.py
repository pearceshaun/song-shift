"""Tests for AppleMusicProvider."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)

from song_shift.config import CredentialStore
from song_shift.models import Playlist, Track
from song_shift.providers.apple_music import (
    AppleMusicProvider,
    generate_developer_token,
)


def _generate_test_ec_key() -> str:
    """Generate a real ES256 private key in PEM format for testing."""
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    ).decode()


SAMPLE_PRIVATE_KEY = _generate_test_ec_key()


def _make_song(
    id="12345",
    name="Test Song",
    artist_name="Test Artist",
    album_name="Test Album",
    isrc="USRC12345678",
    duration_ms=240000,
):
    """Create a mock Apple Music API song object."""
    return {
        "id": id,
        "type": "songs",
        "attributes": {
            "name": name,
            "artistName": artist_name,
            "albumName": album_name,
            "isrc": isrc,
            "durationInMillis": duration_ms,
        },
    }


def _make_playlist_response(
    id="p.abc123",
    name="My Playlist",
    description="A test playlist",
):
    """Create a mock Apple Music API playlist object."""
    return {
        "id": id,
        "type": "library-playlists",
        "attributes": {
            "name": name,
            "description": {"standard": description},
        },
    }


@pytest.fixture
def credential_store(tmp_path):
    """Create a CredentialStore using a temp directory."""
    return CredentialStore(config_dir=tmp_path)


@pytest.fixture
def authed_store(credential_store):
    """CredentialStore with Apple Music credentials pre-loaded."""
    credential_store.save(
        "apple_music",
        {
            "developer_token": "dev_token_123",
            "user_token": "user_token_456",
            "key_id": "KEY123",
            "team_id": "TEAM456",
            "storefront": "gb",
        },
    )
    return credential_store


@pytest.fixture
def provider(authed_store):
    """Create an AppleMusicProvider with credentials."""
    return AppleMusicProvider(credential_store=authed_store)


@pytest.fixture
def mock_client(provider):
    """Patch httpx.Client for the provider and return the mock."""
    mock = MagicMock()
    provider._client = mock
    return mock


class TestGenerateDeveloperToken:
    def test_generate_developer_token(self):
        """Generates valid JWT with correct claims and ES256 signing."""
        import jwt as pyjwt

        token = generate_developer_token(
            team_id="TEAM123",
            key_id="KEY456",
            private_key=SAMPLE_PRIVATE_KEY,
        )

        # Decode without verification to check claims
        decoded = pyjwt.decode(token, options={"verify_signature": False})
        assert decoded["iss"] == "TEAM123"
        assert "iat" in decoded
        assert "exp" in decoded
        # exp should be ~180 days after iat
        assert decoded["exp"] - decoded["iat"] == 180 * 24 * 60 * 60

        # Check header
        header = pyjwt.get_unverified_header(token)
        assert header["alg"] == "ES256"
        assert header["kid"] == "KEY456"


class TestAppleMusicAuthentication:
    def test_authenticate_stores_credentials(self, credential_store, tmp_path):
        """Stores all auth components in CredentialStore."""
        provider = AppleMusicProvider(credential_store=credential_store)
        key_file = tmp_path / "key.p8"
        key_file.write_text(SAMPLE_PRIVATE_KEY)

        with patch("click.prompt") as mock_prompt:
            mock_prompt.side_effect = [
                str(key_file),  # key path
                "KEY123",  # key id
                "TEAM456",  # team id
                "gb",  # storefront
                "user_token_xyz",  # user token
            ]
            provider.authenticate()

        creds = credential_store.get("apple_music")
        assert creds is not None
        assert creds["developer_token"]  # should be a JWT string
        assert creds["user_token"] == "user_token_xyz"
        assert creds["key_id"] == "KEY123"
        assert creds["team_id"] == "TEAM456"
        assert creds["storefront"] == "gb"

    def test_is_authenticated_with_valid_credentials(self, authed_store):
        """Returns True when all credentials present."""
        provider = AppleMusicProvider(credential_store=authed_store)
        assert provider.is_authenticated() is True

    def test_is_authenticated_with_missing_credentials(self, credential_store):
        """Returns False when credentials incomplete."""
        provider = AppleMusicProvider(credential_store=credential_store)
        assert provider.is_authenticated() is False

        # Also test with partial credentials
        credential_store.save("apple_music", {"developer_token": "tok"})
        assert provider.is_authenticated() is False


class TestAppleMusicPlaylists:
    def test_list_playlists(self, provider, mock_client):
        """Calls API, handles pagination, returns mapped Playlists."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                _make_playlist_response("p.1", "Playlist 1", "First"),
                _make_playlist_response("p.2", "Playlist 2", "Second"),
            ],
            "next": None,
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = provider.list_playlists()

        assert len(result) == 2
        assert isinstance(result[0], Playlist)
        assert result[0].id == "p.1"
        assert result[0].name == "Playlist 1"
        assert result[0].description == "First"
        assert result[0].provider == "apple_music"
        assert result[1].name == "Playlist 2"

    def test_get_playlist_tracks(self, provider, mock_client):
        """Calls API, handles pagination, returns mapped Tracks with ISRC."""
        page1_response = MagicMock()
        page1_response.json.return_value = {
            "data": [_make_song("1", "Song 1", "Artist 1", "Album 1", "ISRC001")],
            "next": "/me/library/playlists/p.1/tracks?offset=1",
        }
        page1_response.raise_for_status = MagicMock()

        page2_response = MagicMock()
        page2_response.json.return_value = {
            "data": [_make_song("2", "Song 2", "Artist 2", "Album 2", "ISRC002")],
            "next": None,
        }
        page2_response.raise_for_status = MagicMock()

        mock_client.get.side_effect = [page1_response, page2_response]

        result = provider.get_playlist_tracks("p.1")

        assert len(result) == 2
        assert isinstance(result[0], Track)
        assert result[0].title == "Song 1"
        assert result[0].artist == "Artist 1"
        assert result[0].isrc == "ISRC001"
        assert result[0].provider_id == "1"
        assert result[0].provider == "apple_music"
        assert result[1].title == "Song 2"
        assert result[1].isrc == "ISRC002"


class TestAppleMusicSearch:
    def test_search_track_by_isrc(self, provider, mock_client):
        """Calls ISRC filter endpoint, returns Track or None."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [_make_song(isrc="USRC12345678")],
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = provider.search_track_by_isrc("USRC12345678")

        assert result is not None
        assert isinstance(result, Track)
        assert result.isrc == "USRC12345678"
        assert result.title == "Test Song"
        mock_client.get.assert_called_once_with(
            "/catalog/gb/songs",
            params={"filter[isrc]": "USRC12345678"},
        )

    def test_search_track(self, provider, mock_client):
        """Calls search endpoint, returns list of mapped Tracks."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": {
                "songs": {
                    "data": [
                        _make_song("1", "Found Song", "Found Artist", "Found Album"),
                    ]
                }
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = provider.search_track("Found Artist Found Song")

        assert len(result) == 1
        assert isinstance(result[0], Track)
        assert result[0].title == "Found Song"
        assert result[0].artist == "Found Artist"
        mock_client.get.assert_called_once_with(
            "/catalog/gb/search",
            params={"types": "songs", "term": "Found Artist Found Song"},
        )


class TestAppleMusicPlaylistManagement:
    def test_create_playlist(self, provider, mock_client):
        """POSTs to API, returns mapped Playlist."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                _make_playlist_response("p.new", "New Playlist", "A new one"),
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        result = provider.create_playlist("New Playlist", "A new one")

        assert isinstance(result, Playlist)
        assert result.id == "p.new"
        assert result.name == "New Playlist"
        assert result.description == "A new one"
        assert result.provider == "apple_music"
        mock_client.post.assert_called_once_with(
            "/me/library/playlists",
            json={
                "attributes": {
                    "name": "New Playlist",
                    "description": "A new one",
                }
            },
        )

    def test_add_tracks_to_playlist(self, provider, mock_client):
        """POSTs track IDs, returns count."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        result = provider.add_tracks_to_playlist(
            "p.abc123", ["111", "222", "333"]
        )

        assert result == 3
        mock_client.post.assert_called_once_with(
            "/me/library/playlists/p.abc123/tracks",
            json={
                "data": [
                    {"id": "111", "type": "songs"},
                    {"id": "222", "type": "songs"},
                    {"id": "333", "type": "songs"},
                ]
            },
        )


class TestAppleMusicErrorHandling:
    def test_api_error_handling(self, provider, mock_client):
        """Raises appropriate exceptions on error responses."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=MagicMock(status_code=401),
        )
        mock_client.get.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            provider.search_track("test query")
