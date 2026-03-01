from abc import ABC, abstractmethod

from song_shift.models import Playlist, Track

_registry: dict[str, type["MusicProvider"]] = {}


def register_provider(cls: type["MusicProvider"]) -> type["MusicProvider"]:
    """Register a provider class in the registry."""
    _registry[cls.name] = cls
    return cls


def get_provider(name: str) -> type["MusicProvider"] | None:
    """Retrieve a provider class by name."""
    return _registry.get(name)


def list_providers() -> list[str]:
    """Return list of registered provider names."""
    return list(_registry.keys())


class MusicProvider(ABC):
    """Abstract base class for music service providers."""

    name: str

    @abstractmethod
    def authenticate(self) -> None:
        """Run interactive auth flow, store credentials."""
        ...

    @abstractmethod
    def is_authenticated(self) -> bool:
        """Check if valid credentials exist."""
        ...

    @abstractmethod
    def list_playlists(self) -> list[Playlist]:
        """Return user's playlists (metadata only, no tracks)."""
        ...

    @abstractmethod
    def get_playlist_tracks(self, playlist_id: str) -> list[Track]:
        """Return tracks in a playlist."""
        ...

    @abstractmethod
    def search_track(self, query: str) -> list[Track]:
        """Search the catalog."""
        ...

    @abstractmethod
    def search_track_by_isrc(self, isrc: str) -> Track | None:
        """Exact ISRC lookup."""
        ...

    @abstractmethod
    def create_playlist(self, name: str, description: str) -> Playlist:
        """Create empty playlist."""
        ...

    @abstractmethod
    def add_tracks_to_playlist(self, playlist_id: str, track_ids: list[str]) -> int:
        """Add tracks, return count added."""
        ...
