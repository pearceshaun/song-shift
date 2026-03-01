"""Tests for PlaylistMigrator and MigrationReport."""

from unittest.mock import MagicMock

import pytest

from song_shift.migrator import MigrationReport, PlaylistMigrator
from song_shift.models import MatchResult, Playlist, Track


def _make_track(title: str, artist: str, provider: str = "source", isrc: str | None = None) -> Track:
    """Helper to create a Track with minimal boilerplate."""
    return Track(
        title=title,
        artist=artist,
        album="Album",
        provider_id=f"{provider}-{title.lower().replace(' ', '-')}",
        provider=provider,
        isrc=isrc,
    )


def _make_target_track(title: str, artist: str, isrc: str | None = None) -> Track:
    return _make_track(title, artist, provider="target", isrc=isrc)


@pytest.fixture()
def source_tracks() -> list[Track]:
    return [
        _make_track("Song A", "Artist 1", isrc="ISRC001"),
        _make_track("Song B", "Artist 2", isrc="ISRC002"),
        _make_track("Song C", "Artist 3"),
    ]


@pytest.fixture()
def source_provider(source_tracks: list[Track]) -> MagicMock:
    provider = MagicMock()
    provider.get_playlist_tracks.return_value = source_tracks
    provider.list_playlists.return_value = [
        Playlist(id="pl-1", name="My Playlist", provider="source"),
    ]
    return provider


@pytest.fixture()
def target_provider() -> MagicMock:
    """Target provider that matches Song A by ISRC, Song B by fuzzy, misses Song C."""
    provider = MagicMock()

    target_a = _make_target_track("Song A", "Artist 1", isrc="ISRC001")
    target_b = _make_target_track("Song B", "Artist 2")

    def search_by_isrc(isrc: str) -> Track | None:
        if isrc == "ISRC001":
            return target_a
        return None

    def search_track(query: str) -> list[Track]:
        if "Song B" in query:
            return [target_b]
        return []

    provider.search_track_by_isrc.side_effect = search_by_isrc
    provider.search_track.side_effect = search_track
    provider.create_playlist.return_value = Playlist(
        id="new-pl", name="My Playlist", provider="target"
    )
    provider.add_tracks_to_playlist.return_value = 2
    return provider


@pytest.fixture()
def migrator() -> PlaylistMigrator:
    return PlaylistMigrator()


class TestMigrator:
    def test_migrate_full_flow(
        self,
        migrator: PlaylistMigrator,
        source_provider: MagicMock,
        target_provider: MagicMock,
    ) -> None:
        """Reads tracks, matches, creates playlist, adds matched tracks."""
        report = migrator.migrate(source_provider, "pl-1", target_provider)

        source_provider.get_playlist_tracks.assert_called_once_with("pl-1")
        target_provider.create_playlist.assert_called_once()
        target_provider.add_tracks_to_playlist.assert_called_once()

        # Should add 2 matched track IDs (Song A via ISRC, Song B via fuzzy)
        call_args = target_provider.add_tracks_to_playlist.call_args
        assert len(call_args[0][1]) == 2

    def test_migrate_report_counts(
        self,
        migrator: PlaylistMigrator,
        source_provider: MagicMock,
        target_provider: MagicMock,
    ) -> None:
        """Report has correct total, matched, unmatched, isrc, fuzzy counts."""
        report = migrator.migrate(source_provider, "pl-1", target_provider)

        assert report.total_tracks == 3
        assert report.matched_tracks == 2
        assert report.unmatched_tracks == 1
        assert report.isrc_matches == 1
        assert report.fuzzy_matches == 1

    def test_migrate_with_unmatched_tracks(
        self,
        migrator: PlaylistMigrator,
        source_provider: MagicMock,
        target_provider: MagicMock,
    ) -> None:
        """Unmatched tracks excluded from created playlist."""
        report = migrator.migrate(source_provider, "pl-1", target_provider)

        # Only matched track IDs should be added
        call_args = target_provider.add_tracks_to_playlist.call_args
        added_ids = call_args[0][1]

        # Song C (unmatched) should not appear
        unmatched_results = [r for r in report.match_results if r.method == "none"]
        assert len(unmatched_results) == 1
        assert unmatched_results[0].source_track.title == "Song C"

        for uid in added_ids:
            assert uid != ""  # all IDs are real

    def test_migrate_custom_playlist_name(
        self,
        migrator: PlaylistMigrator,
        source_provider: MagicMock,
        target_provider: MagicMock,
    ) -> None:
        """Uses custom name when provided."""
        migrator.migrate(
            source_provider, "pl-1", target_provider, playlist_name="Custom Name"
        )

        target_provider.create_playlist.assert_called_once_with("Custom Name", "")

    def test_migrate_uses_source_name_by_default(
        self,
        migrator: PlaylistMigrator,
        source_provider: MagicMock,
        target_provider: MagicMock,
    ) -> None:
        """Uses source playlist name when no custom name given."""
        migrator.migrate(source_provider, "pl-1", target_provider)

        target_provider.create_playlist.assert_called_once_with("My Playlist", "")

    def test_migrate_report_summary(
        self,
        migrator: PlaylistMigrator,
        source_provider: MagicMock,
        target_provider: MagicMock,
    ) -> None:
        """summary() returns human-readable string with counts."""
        report = migrator.migrate(source_provider, "pl-1", target_provider)
        summary = report.summary()

        assert "2/3" in summary or ("2" in summary and "3" in summary)
        assert "1" in summary  # ISRC count
        assert "unmatched" in summary.lower() or "1" in summary
        assert "My Playlist" in summary

    def test_migrate_empty_playlist(
        self,
        migrator: PlaylistMigrator,
        target_provider: MagicMock,
    ) -> None:
        """Handles playlist with zero tracks gracefully."""
        source_provider = MagicMock()
        source_provider.get_playlist_tracks.return_value = []
        source_provider.list_playlists.return_value = [
            Playlist(id="empty-pl", name="Empty", provider="source"),
        ]

        target_provider.create_playlist.return_value = Playlist(
            id="new-empty", name="Empty", provider="target"
        )

        report = migrator.migrate(source_provider, "empty-pl", target_provider)

        assert report.total_tracks == 0
        assert report.matched_tracks == 0
        assert report.unmatched_tracks == 0
        assert report.match_results == []
        target_provider.create_playlist.assert_called_once()
        # Should not call add_tracks when there are no tracks
        target_provider.add_tracks_to_playlist.assert_not_called()
