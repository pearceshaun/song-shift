"""Tests for TrackMatcher — ISRC primary + fuzzy fallback."""

from unittest.mock import MagicMock, call

from song_shift.matcher import TrackMatcher
from song_shift.models import Track


def _make_track(
    title: str = "Song",
    artist: str = "Artist",
    album: str = "Album",
    provider_id: str = "123",
    provider: str = "source",
    isrc: str | None = "USRC12345",
) -> Track:
    return Track(
        title=title,
        artist=artist,
        album=album,
        provider_id=provider_id,
        provider=provider,
        isrc=isrc,
    )


def _make_target_track(
    title: str = "Song",
    artist: str = "Artist",
    album: str = "Album",
    provider_id: str = "456",
) -> Track:
    return Track(
        title=title,
        artist=artist,
        album=album,
        provider_id=provider_id,
        provider="target",
    )


class TestTrackMatcher:
    def test_isrc_match_found(self):
        """Track with ISRC matches via provider.search_track_by_isrc, confidence=1.0."""
        matcher = TrackMatcher()
        source = _make_track(isrc="USRC12345")
        target = _make_target_track()

        provider = MagicMock()
        provider.search_track_by_isrc.return_value = target

        result = matcher.match_track(source, provider)

        provider.search_track_by_isrc.assert_called_once_with("USRC12345")
        assert result.is_matched
        assert result.matched_track == target
        assert result.method == "isrc"
        assert result.confidence == 1.0

    def test_isrc_match_not_found_falls_back_to_fuzzy(self):
        """ISRC returns None, fuzzy search finds match."""
        matcher = TrackMatcher()
        source = _make_track(title="Yesterday", artist="The Beatles", isrc="GBAYE0000001")
        target = _make_target_track(title="Yesterday", artist="The Beatles")

        provider = MagicMock()
        provider.search_track_by_isrc.return_value = None
        provider.search_track.return_value = [target]

        result = matcher.match_track(source, provider)

        provider.search_track_by_isrc.assert_called_once_with("GBAYE0000001")
        assert result.is_matched
        assert result.matched_track == target
        assert result.method == "fuzzy"
        assert result.confidence > 0.8

    def test_fuzzy_match_above_threshold(self):
        """Fuzzy score >= 80 returns match with method='fuzzy'."""
        matcher = TrackMatcher()
        source = _make_track(title="Come Together", artist="The Beatles", isrc=None)
        target = _make_target_track(title="Come Together", artist="The Beatles")

        provider = MagicMock()
        provider.search_track.return_value = [target]

        result = matcher.match_track(source, provider)

        assert result.is_matched
        assert result.method == "fuzzy"
        assert result.confidence >= 0.8

    def test_fuzzy_match_below_threshold(self):
        """Fuzzy score < 80 returns no match, method='none'."""
        matcher = TrackMatcher()
        source = _make_track(title="Come Together", artist="The Beatles", isrc=None)
        # Completely different track — low fuzzy score
        unrelated = _make_target_track(
            title="Bohemian Rhapsody", artist="Queen"
        )

        provider = MagicMock()
        provider.search_track.return_value = [unrelated]

        result = matcher.match_track(source, provider)

        assert not result.is_matched
        assert result.matched_track is None
        assert result.method == "none"
        assert result.confidence == 0.0

    def test_no_isrc_goes_straight_to_fuzzy(self):
        """Track without ISRC skips ISRC lookup."""
        matcher = TrackMatcher()
        source = _make_track(title="Let It Be", artist="The Beatles", isrc=None)
        target = _make_target_track(title="Let It Be", artist="The Beatles")

        provider = MagicMock()
        provider.search_track.return_value = [target]

        result = matcher.match_track(source, provider)

        provider.search_track_by_isrc.assert_not_called()
        assert result.is_matched
        assert result.method == "fuzzy"

    def test_wrong_artist_rejected_with_weighted_scoring(self):
        """A candidate with matching title but wrong artist scores below threshold."""
        matcher = TrackMatcher()
        source = _make_track(title="Paper Boats", artist="Hania Rani", isrc=None)
        wrong_artist = _make_target_track(title="Paper Boats", artist="Zac")

        provider = MagicMock()
        provider.search_track.return_value = [wrong_artist]

        result = matcher.match_track(source, provider)

        assert not result.is_matched
        assert result.method == "none"

    def test_fallback_query_finds_match(self):
        """When first query misses, title-only query finds the right track."""
        matcher = TrackMatcher()
        source = _make_track(title="Bella", artist="Hania Rani", isrc=None)
        target = _make_target_track(title="Bella", artist="Hania Rani")

        provider = MagicMock()
        # First query "Bella Hania Rani" returns nothing,
        # second "Hania Rani Bella" returns nothing,
        # third "Bella" returns the match
        provider.search_track.side_effect = [[], [], [target]]

        result = matcher.match_track(source, provider)

        assert result.is_matched
        assert result.matched_track == target
        assert result.method == "fuzzy"
        assert provider.search_track.call_count == 3

    def test_match_tracks_processes_all(self):
        """match_tracks returns a MatchResult for every input track."""
        matcher = TrackMatcher()
        tracks = [
            _make_track(title="Song A", provider_id="1", isrc=None),
            _make_track(title="Song B", provider_id="2", isrc=None),
            _make_track(title="Song C", provider_id="3", isrc=None),
        ]

        provider = MagicMock()
        # Return empty search results — all will be unmatched
        provider.search_track.return_value = []

        results = matcher.match_tracks(tracks, provider)

        assert len(results) == 3
        assert all(r.source_track in tracks for r in results)

    def test_match_tracks_calls_progress_callback(self):
        """on_progress called once per track with (current, total)."""
        matcher = TrackMatcher()
        tracks = [
            _make_track(title="Song A", provider_id="1", isrc=None),
            _make_track(title="Song B", provider_id="2", isrc=None),
        ]

        provider = MagicMock()
        provider.search_track.return_value = []

        progress = MagicMock()
        matcher.match_tracks(tracks, provider, on_progress=progress)

        assert progress.call_count == 2
        progress.assert_has_calls([call(1, 2), call(2, 2)])
