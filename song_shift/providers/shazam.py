"""Shazam music service provider using CSV import and shazamio for search."""

import asyncio
import csv
from pathlib import Path

from shazamio import Shazam

from song_shift.config import CredentialStore
from song_shift.models import Playlist, Track
from song_shift.providers.base import MusicProvider, register_provider

_REQUIRED_HEADERS = {"Title", "Artist", "TrackKey"}


def _map_search_hit(hit: dict) -> Track:
    """Map a shazamio search hit to a Track model."""
    heading = hit.get("heading", {})
    return Track(
        title=heading.get("title", ""),
        artist=heading.get("subtitle", ""),
        album="",
        provider_id=hit.get("key", ""),
        provider="shazam",
        isrc=None,
        duration_ms=None,
    )


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
                next(reader)  # skip "Shazam Library" metadata line
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

    def _get_csv_path(self) -> Path:
        """Return the stored CSV path, raising if not authenticated."""
        creds = self._credential_store.get("shazam")
        if not creds:
            raise RuntimeError("Not authenticated -- call authenticate() first")
        return Path(creds["csv_path"])

    def _parse_csv(self) -> list[Track]:
        """Parse the CSV file and return Track objects, skipping empty rows."""
        path = self._get_csv_path()
        tracks: list[Track] = []
        with open(path, newline="") as f:
            next(f)  # skip "Shazam Library" metadata line
            reader = csv.DictReader(f)
            for row in reader:
                title = row.get("Title", "").strip()
                artist = row.get("Artist", "").strip()
                if not title and not artist:
                    continue
                tracks.append(
                    Track(
                        title=title,
                        artist=artist,
                        album="",
                        provider_id=row.get("TrackKey", "").strip(),
                        provider="shazam",
                        isrc=None,
                        duration_ms=None,
                    )
                )
        return tracks

    def list_playlists(self) -> list[Playlist]:
        """Return a single synthetic playlist from the CSV file."""
        tracks = self._parse_csv()
        return [
            Playlist(
                id="shazam-library",
                name="My Shazam Tracks",
                track_count=len(tracks),
                provider="shazam",
            )
        ]

    def get_playlist_tracks(self, playlist_id: str) -> list[Track]:
        """Parse CSV and return Track objects."""
        return self._parse_csv()

    def search_track(self, query: str) -> list[Track]:
        """Search using shazamio."""
        shazam = Shazam()
        result = asyncio.run(shazam.search_track(query=query, limit=5))
        hits = result.get("tracks", {}).get("hits", [])
        return [_map_search_hit(hit) for hit in hits]

    def search_track_by_isrc(self, isrc: str) -> Track | None:
        """Not supported by Shazam."""
        return None

    def create_playlist(self, name: str, description: str) -> Playlist:
        """Not supported -- Shazam is read-only."""
        raise NotImplementedError(
            "Shazam is a read-only source and does not support playlist creation"
        )

    def add_tracks_to_playlist(self, playlist_id: str, track_ids: list[str]) -> int:
        """Not supported -- Shazam is read-only."""
        raise NotImplementedError(
            "Shazam is a read-only source and does not support playlist creation"
        )
