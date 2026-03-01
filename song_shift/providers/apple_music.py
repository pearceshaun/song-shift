"""Apple Music provider using MusicKit REST API via httpx."""

import time

import click
import httpx
import jwt

from song_shift.config import CredentialStore
from song_shift.models import Playlist, Track
from song_shift.providers.base import MusicProvider, register_provider

API_BASE = "https://api.music.apple.com/v1"
MAX_TRACKS = 500


def _map_track(song: dict) -> Track:
    """Map an Apple Music API song object to our Track model."""
    attrs = song["attributes"]
    return Track(
        title=attrs["name"],
        artist=attrs["artistName"],
        album=attrs["albumName"],
        isrc=attrs.get("isrc"),
        duration_ms=attrs.get("durationInMillis"),
        provider_id=song["id"],
        provider="apple_music",
    )


def _map_playlist(playlist: dict) -> Playlist:
    """Map an Apple Music API playlist object to our Playlist model."""
    attrs = playlist["attributes"]
    return Playlist(
        id=playlist["id"],
        name=attrs["name"],
        description=attrs.get("description", {}).get("standard", ""),
        track_count=0,
        provider="apple_music",
    )


def generate_developer_token(
    team_id: str, key_id: str, private_key: str
) -> str:
    """Generate an Apple Music developer token (JWT signed with ES256).

    Args:
        team_id: Apple Developer team ID.
        key_id: Apple Music key ID from developer portal.
        private_key: Contents of the .p8 private key file.

    Returns:
        Signed JWT string valid for 180 days.
    """
    now = int(time.time())
    payload = {
        "iss": team_id,
        "iat": now,
        "exp": now + (180 * 24 * 60 * 60),  # 180 days
    }
    headers = {
        "alg": "ES256",
        "kid": key_id,
    }
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


@register_provider
class AppleMusicProvider(MusicProvider):
    """Apple Music integration using the MusicKit REST API."""

    name = "apple_music"

    def __init__(self, credential_store: CredentialStore | None = None) -> None:
        self._credential_store = credential_store or CredentialStore()
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        """Get or create an httpx client with auth headers."""
        if self._client is None:
            creds = self._credential_store.get("apple_music")
            if creds is None:
                raise RuntimeError("Not authenticated with Apple Music")
            self._client = httpx.Client(
                base_url=API_BASE,
                headers={
                    "Authorization": f"Bearer {creds['developer_token']}",
                    "Music-User-Token": creds["user_token"],
                },
            )
        return self._client

    def authenticate(self) -> None:
        """Run interactive auth flow, store credentials."""
        key_path = click.prompt("Path to Apple Music .p8 private key file")
        key_id = click.prompt("Apple Music Key ID")
        team_id = click.prompt("Apple Developer Team ID")
        storefront = click.prompt("Storefront code", default="gb")
        user_token = click.prompt("Music User Token")

        with open(key_path) as f:
            private_key = f.read()

        developer_token = generate_developer_token(team_id, key_id, private_key)

        self._credential_store.save(
            "apple_music",
            {
                "developer_token": developer_token,
                "user_token": user_token,
                "key_id": key_id,
                "team_id": team_id,
                "storefront": storefront,
            },
        )
        # Reset client so next call picks up new credentials
        self._client = None

    def is_authenticated(self) -> bool:
        """Check if valid credentials exist."""
        creds = self._credential_store.get("apple_music")
        if creds is None:
            return False
        return bool(
            creds.get("developer_token") and creds.get("user_token")
        )

    def _get_storefront(self) -> str:
        """Get the storefront code from stored credentials."""
        creds = self._credential_store.get("apple_music")
        if creds and creds.get("storefront"):
            return creds["storefront"]
        return "gb"

    def _paginate(self, url: str, key: str, limit: int = MAX_TRACKS) -> list[dict]:
        """Follow pagination links, collecting items up to limit."""
        client = self._get_client()
        items: list[dict] = []
        next_url: str | None = url

        while next_url and len(items) < limit:
            response = client.get(next_url)
            response.raise_for_status()
            data = response.json()
            items.extend(data.get("data", []))
            next_url = data.get("next")

        return items[:limit]

    def list_playlists(self) -> list[Playlist]:
        """Return user's library playlists."""
        items = self._paginate("/me/library/playlists", "playlists")
        return [_map_playlist(p) for p in items]

    def get_playlist_tracks(self, playlist_id: str) -> list[Track]:
        """Return tracks in a playlist."""
        items = self._paginate(
            f"/me/library/playlists/{playlist_id}/tracks", "tracks"
        )
        return [_map_track(t) for t in items]

    def search_track(self, query: str) -> list[Track]:
        """Search the Apple Music catalog."""
        storefront = self._get_storefront()
        client = self._get_client()
        response = client.get(
            f"/catalog/{storefront}/search",
            params={"types": "songs", "term": query},
        )
        response.raise_for_status()
        data = response.json()
        songs = data.get("results", {}).get("songs", {}).get("data", [])
        return [_map_track(s) for s in songs]

    def search_track_by_isrc(self, isrc: str) -> Track | None:
        """Search by ISRC filter, return first match or None."""
        storefront = self._get_storefront()
        client = self._get_client()
        response = client.get(
            f"/catalog/{storefront}/songs",
            params={"filter[isrc]": isrc},
        )
        response.raise_for_status()
        data = response.json()
        songs = data.get("data", [])
        if songs:
            return _map_track(songs[0])
        return None

    def create_playlist(self, name: str, description: str) -> Playlist:
        """Create an empty playlist in the user's library."""
        client = self._get_client()
        body = {
            "attributes": {
                "name": name,
                "description": description,
            }
        }
        response = client.post("/me/library/playlists", json=body)
        response.raise_for_status()
        data = response.json()
        playlist_data = data["data"][0]
        return _map_playlist(playlist_data)

    def add_tracks_to_playlist(self, playlist_id: str, track_ids: list[str]) -> int:
        """Add tracks to a playlist, return count added."""
        client = self._get_client()
        body = {
            "data": [
                {"id": tid, "type": "songs"} for tid in track_ids
            ]
        }
        response = client.post(
            f"/me/library/playlists/{playlist_id}/tracks", json=body
        )
        response.raise_for_status()
        return len(track_ids)
