"""Shazam music service provider using CSV import and shazamio for search."""

import csv
from pathlib import Path

from song_shift.config import CredentialStore
from song_shift.models import Playlist, Track
from song_shift.providers.base import MusicProvider, register_provider

_REQUIRED_HEADERS = {"Title", "Artist", "TrackKey"}


@register_provider
class ShazamProvider(MusicProvider):
    """Read-only Shazam provider that imports from exported CSV files."""

    name = "shazam"

    def __init__(self, credential_store: CredentialStore | None = None) -> None:
        self._credential_store = credential_store or CredentialStore()

    def authenticate(self) -> None:
        """Prompt for CSV file path, validate, and store in credentials."""
        csv_path = input("Enter path to your SyncedShazams.csv file: ").strip()
        path = Path(csv_path).expanduser().resolve()

        if not path.is_file():
            raise FileNotFoundError(f"CSV file not found: {path}")

        with open(path, newline="") as f:
            reader = csv.reader(f)
            try:
                headers = set(next(reader))
            except StopIteration:
                raise ValueError("CSV file is empty")

        missing = _REQUIRED_HEADERS - headers
        if missing:
            raise ValueError(f"CSV missing required headers: {', '.join(sorted(missing))}")

        self._credential_store.save("shazam", {"csv_path": str(path)})

    def is_authenticated(self) -> bool:
        """Check if credentials exist and the CSV file still exists on disk."""
        creds = self._credential_store.get("shazam")
        if not creds:
            return False
        return Path(creds["csv_path"]).is_file()

    def list_playlists(self) -> list[Playlist]:
        """Return a single synthetic playlist from the CSV file."""
        raise NotImplementedError

    def get_playlist_tracks(self, playlist_id: str) -> list[Track]:
        """Parse CSV and return Track objects."""
        raise NotImplementedError

    def search_track(self, query: str) -> list[Track]:
        """Search using shazamio."""
        raise NotImplementedError

    def search_track_by_isrc(self, isrc: str) -> Track | None:
        """Not supported by Shazam."""
        raise NotImplementedError

    def create_playlist(self, name: str, description: str) -> Playlist:
        """Not supported -- Shazam is read-only."""
        raise NotImplementedError

    def add_tracks_to_playlist(self, playlist_id: str, track_ids: list[str]) -> int:
        """Not supported -- Shazam is read-only."""
        raise NotImplementedError
