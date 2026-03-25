"""Tests for YouTubeProvider."""

from unittest.mock import MagicMock, patch

import pytest

from song_shift.models import Playlist, Track
from song_shift.providers.youtube import (
    YouTubeProvider,
    _parse_chapter_title,
    _parse_description_timestamps,
)


@pytest.fixture
def provider():
    """Create a YouTubeProvider instance."""
    return YouTubeProvider()


def _make_info(
    title="Test Video",
    chapters=None,
    description="",
):
    """Build a yt-dlp info dict for testing."""
    info = {"title": title, "description": description}
    if chapters is not None:
        info["chapters"] = chapters
    return info


class TestYouTubeAuthentication:
    def test_authenticate_succeeds_silently(self, provider):
        """authenticate() does not raise; no credentials stored."""
        provider.authenticate()  # should not raise

    def test_is_authenticated_always_true(self, provider):
        """is_authenticated() returns True (no auth needed for public videos)."""
        assert provider.is_authenticated() is True

    def test_search_track_by_isrc_returns_none(self, provider):
        """search_track_by_isrc() returns None."""
        assert provider.search_track_by_isrc("USRC17000001") is None


class TestYouTubeChapterParsing:
    def test_get_tracks_from_chapters(self, provider):
        """Given video info with chapters, returns Track objects with correct artist/title."""
        chapters = [
            {"title": "Daft Punk - Around the World", "start_time": 0, "end_time": 210},
            {"title": "Justice - Genesis", "start_time": 210, "end_time": 450},
        ]
        info = _make_info(chapters=chapters)

        with patch("song_shift.providers.youtube.yt_dlp") as mock_yt_dlp:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = info
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_yt_dlp.YoutubeDL.return_value = mock_ydl

            tracks = provider.get_playlist_tracks("https://youtu.be/test")

        assert len(tracks) == 2
        assert tracks[0].artist == "Daft Punk"
        assert tracks[0].title == "Around the World"
        assert tracks[1].artist == "Justice"
        assert tracks[1].title == "Genesis"

    def test_get_tracks_strips_track_numbers(self, provider):
        """Chapter titles like '1. Artist - Title' have number stripped."""
        chapters = [
            {"title": "1. Daft Punk - Around the World", "start_time": 0, "end_time": 210},
        ]
        info = _make_info(chapters=chapters)

        with patch("song_shift.providers.youtube.yt_dlp") as mock_yt_dlp:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = info
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_yt_dlp.YoutubeDL.return_value = mock_ydl

            tracks = provider.get_playlist_tracks("https://youtu.be/test")

        assert tracks[0].artist == "Daft Punk"
        assert tracks[0].title == "Around the World"

    def test_get_tracks_colon_separator(self, provider):
        """Chapter titles like 'Artist: Title' are split correctly."""
        chapters = [
            {"title": "Daft Punk: Around the World", "start_time": 0, "end_time": 210},
        ]
        info = _make_info(chapters=chapters)

        with patch("song_shift.providers.youtube.yt_dlp") as mock_yt_dlp:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = info
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_yt_dlp.YoutubeDL.return_value = mock_ydl

            tracks = provider.get_playlist_tracks("https://youtu.be/test")

        assert tracks[0].artist == "Daft Punk"
        assert tracks[0].title == "Around the World"

    def test_get_tracks_by_separator(self, provider):
        """Chapter titles like 'Title by Artist' are split correctly (artist/title swapped)."""
        chapters = [
            {"title": "Around the World by Daft Punk", "start_time": 0, "end_time": 210},
        ]
        info = _make_info(chapters=chapters)

        with patch("song_shift.providers.youtube.yt_dlp") as mock_yt_dlp:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = info
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_yt_dlp.YoutubeDL.return_value = mock_ydl

            tracks = provider.get_playlist_tracks("https://youtu.be/test")

        assert tracks[0].artist == "Daft Punk"
        assert tracks[0].title == "Around the World"

    def test_get_tracks_no_separator_uses_raw_title(self, provider):
        """Chapter titles with no delimiter set artist='' and title=full string."""
        chapters = [
            {"title": "SomeTrackWithNoDelimiter", "start_time": 0, "end_time": 210},
        ]
        info = _make_info(chapters=chapters)

        with patch("song_shift.providers.youtube.yt_dlp") as mock_yt_dlp:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = info
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_yt_dlp.YoutubeDL.return_value = mock_ydl

            tracks = provider.get_playlist_tracks("https://youtu.be/test")

        assert tracks[0].artist == ""
        assert tracks[0].title == "SomeTrackWithNoDelimiter"


class TestYouTubeDescriptionFallback:
    def test_get_tracks_falls_back_to_description(self, provider):
        """When chapters absent, parses description timestamps."""
        info = _make_info(
            description="0:00 Daft Punk - Around the World\n3:30 Justice - Genesis"
        )

        with patch("song_shift.providers.youtube.yt_dlp") as mock_yt_dlp:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = info
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_yt_dlp.YoutubeDL.return_value = mock_ydl

            tracks = provider.get_playlist_tracks("https://youtu.be/test")

        assert len(tracks) == 2
        assert tracks[0].artist == "Daft Punk"
        assert tracks[0].title == "Around the World"
        assert tracks[1].artist == "Justice"
        assert tracks[1].title == "Genesis"

    def test_description_handles_hhmmss_format(self, provider):
        """Timestamps like '1:23:45 Artist - Title' are parsed."""
        info = _make_info(description="1:23:45 Daft Punk - Around the World")

        with patch("song_shift.providers.youtube.yt_dlp") as mock_yt_dlp:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = info
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_yt_dlp.YoutubeDL.return_value = mock_ydl

            tracks = provider.get_playlist_tracks("https://youtu.be/test")

        assert len(tracks) == 1
        assert tracks[0].artist == "Daft Punk"
        assert tracks[0].title == "Around the World"

    def test_description_ignores_non_timestamp_lines(self, provider):
        """Lines without timestamps are skipped."""
        info = _make_info(
            description="Check out this mix!\n0:00 Daft Punk - Around the World\nEnjoy!"
        )

        with patch("song_shift.providers.youtube.yt_dlp") as mock_yt_dlp:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = info
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_yt_dlp.YoutubeDL.return_value = mock_ydl

            tracks = provider.get_playlist_tracks("https://youtu.be/test")

        assert len(tracks) == 1
        assert tracks[0].artist == "Daft Punk"


class TestYouTubePlaylistMetadata:
    def test_list_playlists_returns_synthetic_playlist(self, provider):
        """Returns single Playlist with video title as name."""
        info = _make_info(title="Best DJ Mix 2024", chapters=[
            {"title": "Track 1", "start_time": 0, "end_time": 100},
        ])

        with patch("song_shift.providers.youtube.yt_dlp") as mock_yt_dlp:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = info
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_yt_dlp.YoutubeDL.return_value = mock_ydl

            playlists = provider.list_playlists("https://youtu.be/test")

        assert len(playlists) == 1
        assert isinstance(playlists[0], Playlist)
        assert playlists[0].name == "Best DJ Mix 2024"
        assert playlists[0].track_count == 1
        assert playlists[0].provider == "youtube"

    def test_get_playlist_tracks_uses_url_as_id(self, provider):
        """playlist_id parameter is passed to yt-dlp as the URL."""
        info = _make_info(chapters=[
            {"title": "Artist - Title", "start_time": 0, "end_time": 100},
        ])
        url = "https://www.youtube.com/watch?v=abc123"

        with patch("song_shift.providers.youtube.yt_dlp") as mock_yt_dlp:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = info
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_yt_dlp.YoutubeDL.return_value = mock_ydl

            provider.get_playlist_tracks(url)

        mock_ydl.extract_info.assert_called_once_with(url, download=False)

    def test_tracks_have_youtube_provider_fields(self, provider):
        """provider='youtube', album='', isrc=None, duration_ms set from chapter duration."""
        chapters = [
            {"title": "Daft Punk - Around the World", "start_time": 0, "end_time": 210},
        ]
        info = _make_info(chapters=chapters)

        with patch("song_shift.providers.youtube.yt_dlp") as mock_yt_dlp:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = info
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_yt_dlp.YoutubeDL.return_value = mock_ydl

            tracks = provider.get_playlist_tracks("https://youtu.be/test")

        assert tracks[0].provider == "youtube"
        assert tracks[0].album == ""
        assert tracks[0].isrc is None
        assert tracks[0].duration_ms == 210000


class TestYouTubeReadOnly:
    def test_create_playlist_raises_not_implemented(self, provider):
        """Raises NotImplementedError with 'read-only' in message."""
        with pytest.raises(NotImplementedError, match="read-only"):
            provider.create_playlist("My Playlist", "Description")

    def test_add_tracks_raises_not_implemented(self, provider):
        """Raises NotImplementedError with 'read-only' in message."""
        with pytest.raises(NotImplementedError, match="read-only"):
            provider.add_tracks_to_playlist("playlist-id", ["track1"])


class TestYouTubeEdgeCases:
    def test_empty_chapters_falls_back_to_description(self, provider):
        """Empty chapters list triggers description parsing."""
        info = _make_info(
            chapters=[],
            description="0:00 Daft Punk - Around the World",
        )

        with patch("song_shift.providers.youtube.yt_dlp") as mock_yt_dlp:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = info
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_yt_dlp.YoutubeDL.return_value = mock_ydl

            tracks = provider.get_playlist_tracks("https://youtu.be/test")

        assert len(tracks) == 1
        assert tracks[0].artist == "Daft Punk"

    def test_no_chapters_no_description_returns_empty(self, provider):
        """Video with no chapters and no timestamps returns []."""
        info = _make_info(description="Just a cool video, no timestamps here.")

        with patch("song_shift.providers.youtube.yt_dlp") as mock_yt_dlp:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = info
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_yt_dlp.YoutubeDL.return_value = mock_ydl

            tracks = provider.get_playlist_tracks("https://youtu.be/test")

        assert tracks == []

    def test_search_track_returns_empty_list(self, provider):
        """search_track() returns [] (no YouTube catalog search)."""
        assert provider.search_track("Daft Punk") == []
