import pytest

from song_shift.models import Playlist, Track
from song_shift.providers.base import (
    MusicProvider,
    _registry,
    get_provider,
    list_providers,
    register_provider,
)


class ConcreteProvider(MusicProvider):
    """Concrete implementation of MusicProvider for testing."""

    name = "test_provider"

    def authenticate(self) -> None:
        pass

    def is_authenticated(self) -> bool:
        return True

    def list_playlists(self) -> list[Playlist]:
        return []

    def get_playlist_tracks(self, playlist_id: str) -> list[Track]:
        return []

    def search_track(self, query: str) -> list[Track]:
        return []

    def search_track_by_isrc(self, isrc: str) -> Track | None:
        return None

    def create_playlist(self, name: str, description: str) -> Playlist:
        return Playlist(id="1", name=name, description=description)

    def add_tracks_to_playlist(self, playlist_id: str, track_ids: list[str]) -> int:
        return len(track_ids)


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear the provider registry before and after each test."""
    saved = dict(_registry)
    _registry.clear()
    yield
    _registry.clear()
    _registry.update(saved)


class TestMusicProviderABC:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            MusicProvider()

    def test_register_and_get_provider(self):
        register_provider(ConcreteProvider)
        result = get_provider("test_provider")
        assert result is ConcreteProvider

    def test_get_unknown_provider(self):
        result = get_provider("nonexistent")
        assert result is None

    def test_list_registered_providers(self):
        register_provider(ConcreteProvider)
        names = list_providers()
        assert "test_provider" in names
