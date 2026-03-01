"""Shared test fixtures for song-shift test suite."""

import pytest

from song_shift.config import CredentialStore
from song_shift.models import Playlist, Track


@pytest.fixture
def credential_store(tmp_path):
    """Create a CredentialStore using a temp directory."""
    return CredentialStore(config_dir=tmp_path)


@pytest.fixture
def sample_track() -> Track:
    """A reusable sample Track for tests that need a generic track."""
    return Track(
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        provider_id="test-123",
        provider="tidal",
        isrc="USRC17000001",
        duration_ms=240000,
    )


@pytest.fixture
def sample_playlist() -> Playlist:
    """A reusable sample Playlist for tests that need a generic playlist."""
    return Playlist(
        id="pl-test-1",
        name="Test Playlist",
        description="A test playlist",
        track_count=10,
        provider="tidal",
    )


@pytest.fixture
def sample_tracks() -> list[Track]:
    """A list of 3 sample tracks with different attributes for migration tests."""
    return [
        Track(
            title="Song A",
            artist="Artist 1",
            album="Album 1",
            provider_id="src-1",
            provider="source",
            isrc="ISRC001",
        ),
        Track(
            title="Song B",
            artist="Artist 2",
            album="Album 2",
            provider_id="src-2",
            provider="source",
            isrc="ISRC002",
        ),
        Track(
            title="Song C",
            artist="Artist 3",
            album="Album 3",
            provider_id="src-3",
            provider="source",
        ),
    ]
