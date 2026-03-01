"""Tidal music service provider using tidalapi."""

import datetime

import tidalapi

from song_shift.config import CredentialStore
from song_shift.models import Playlist, Track
from song_shift.providers.base import MusicProvider, register_provider


def _map_track(track: tidalapi.Track) -> Track:
    """Map a tidalapi Track to our Track model."""
    return Track(
        title=track.name,
        artist=track.artist.name,
        album=track.album.name,
        isrc=track.isrc,
        duration_ms=track.duration * 1000,
        provider_id=str(track.id),
        provider="tidal",
    )


def _map_playlist(playlist: tidalapi.Playlist) -> Playlist:
    """Map a tidalapi Playlist to our Playlist model."""
    return Playlist(
        id=str(playlist.id),
        name=playlist.name,
        description=playlist.description or "",
        track_count=playlist.num_tracks,
        provider="tidal",
    )


@register_provider
class TidalProvider(MusicProvider):
    """Tidal integration using the tidalapi package."""

    name = "tidal"

    def __init__(self, credential_store: CredentialStore | None = None) -> None:
        self._session = tidalapi.Session()
        self._credential_store = credential_store or CredentialStore()

    def authenticate(self) -> None:
        """Run OAuth2 device code flow and store credentials."""
        self._session.login_oauth_simple()
        self._credential_store.save(
            "tidal",
            {
                "token_type": self._session.token_type,
                "access_token": self._session.access_token,
                "refresh_token": self._session.refresh_token,
                "expiry_time": self._session.expiry_time.isoformat()
                if self._session.expiry_time
                else None,
            },
        )

    def is_authenticated(self) -> bool:
        """Check if valid credentials exist and can load a session."""
        if self._session.check_login():
            return True
        creds = self._credential_store.get("tidal")
        if creds is None:
            return False
        expiry_time = None
        if creds.get("expiry_time"):
            expiry_time = datetime.datetime.fromisoformat(creds["expiry_time"])
        return self._session.load_oauth_session(
            token_type=creds["token_type"],
            access_token=creds["access_token"],
            refresh_token=creds.get("refresh_token"),
            expiry_time=expiry_time,
        )

    def list_playlists(self) -> list[Playlist]:
        """Return user's playlists."""
        playlists = self._session.user.playlists()
        return [_map_playlist(p) for p in playlists]

    def get_playlist_tracks(self, playlist_id: str) -> list[Track]:
        """Return tracks in a playlist."""
        playlist = self._session.playlist(playlist_id)
        tracks = playlist.tracks()
        return [_map_track(t) for t in tracks]

    def search_track(self, query: str) -> list[Track]:
        """Search the Tidal catalog."""
        results = self._session.search(query, models=[tidalapi.Track])
        return [_map_track(t) for t in results["tracks"]]

    def search_track_by_isrc(self, isrc: str) -> Track | None:
        """Search by ISRC, return first exact match or None."""
        results = self._session.search(isrc, models=[tidalapi.Track])
        for track in results["tracks"]:
            if track.isrc == isrc:
                return _map_track(track)
        return None

    def create_playlist(self, name: str, description: str) -> Playlist:
        """Create an empty playlist."""
        playlist = self._session.user.create_playlist(name, description)
        return _map_playlist(playlist)

    def add_tracks_to_playlist(self, playlist_id: str, track_ids: list[str]) -> int:
        """Add tracks to a playlist, return count added."""
        playlist = self._session.playlist(playlist_id)
        added = playlist.add(track_ids)
        return len(added)
