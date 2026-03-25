"""Track matching engine with ISRC primary and fuzzy fallback."""

from collections.abc import Callable

from rapidfuzz.fuzz import token_sort_ratio

from song_shift.models import MatchResult, Track
from song_shift.providers.base import MusicProvider

FUZZY_THRESHOLD = 80
TITLE_WEIGHT = 0.6
ARTIST_WEIGHT = 0.4


def _score_candidate(source: Track, candidate: Track) -> float:
    """Score a candidate using weighted title + artist similarity.

    When the source has an artist, scores title and artist independently
    to avoid false positives where only the title matches (e.g. matching
    "Paper Boats - Zac" when searching for "Paper Boats - Hania Rani").

    When the source has no artist, falls back to combined string matching.
    """
    if source.artist:
        title_score = token_sort_ratio(source.title, candidate.title)
        artist_score = token_sort_ratio(source.artist, candidate.artist)
        return title_score * TITLE_WEIGHT + artist_score * ARTIST_WEIGHT
    # No artist info -- compare combined strings
    source_str = f"{source.title} {source.artist}"
    candidate_str = f"{candidate.title} {candidate.artist}"
    return token_sort_ratio(source_str, candidate_str)


def _build_queries(track: Track) -> list[str]:
    """Build a list of search queries to try, from most to least specific."""
    queries = [f"{track.title} {track.artist}".strip()]
    if track.artist:
        queries.append(f"{track.artist} {track.title}")
        queries.append(track.title)
    return queries


class TrackMatcher:
    """Match source tracks to a target provider using ISRC and fuzzy matching."""

    def match_track(
        self, source_track: Track, target_provider: MusicProvider
    ) -> MatchResult:
        """Match a single source track on the target provider.

        Strategy:
          1. If source has ISRC, try exact ISRC lookup.
          2. Try multiple search queries with weighted title/artist scoring.
          3. Return no-match if nothing scores above threshold.
        """
        # ISRC match (primary)
        if source_track.isrc:
            matched = target_provider.search_track_by_isrc(source_track.isrc)
            if matched is not None:
                return MatchResult(
                    source_track=source_track,
                    matched_track=matched,
                    method="isrc",
                    confidence=1.0,
                )

        # Fuzzy match -- try multiple queries
        best_match: Track | None = None
        best_score: float = 0.0

        for query in _build_queries(source_track):
            candidates = target_provider.search_track(query)
            for candidate in candidates:
                score = _score_candidate(source_track, candidate)
                if score > best_score:
                    best_score = score
                    best_match = candidate

        if best_match is not None and best_score >= FUZZY_THRESHOLD:
            return MatchResult(
                source_track=source_track,
                matched_track=best_match,
                method="fuzzy",
                confidence=best_score / 100,
            )

        # No match
        return MatchResult(
            source_track=source_track,
            matched_track=None,
            method="none",
            confidence=0.0,
        )

    def match_tracks(
        self,
        source_tracks: list[Track],
        target_provider: MusicProvider,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> list[MatchResult]:
        """Match all source tracks against the target provider.

        Args:
            source_tracks: Tracks to match.
            target_provider: Provider to search on.
            on_progress: Optional callback called after each track with (current, total).

        Returns:
            A MatchResult for every input track.
        """
        results: list[MatchResult] = []
        total = len(source_tracks)

        for i, track in enumerate(source_tracks):
            result = self.match_track(track, target_provider)
            results.append(result)
            if on_progress is not None:
                on_progress(i + 1, total)

        return results
