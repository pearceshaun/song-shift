"""Track matching engine with ISRC primary and fuzzy fallback."""

from collections.abc import Callable

from rapidfuzz.fuzz import token_sort_ratio

from song_shift.models import MatchResult, Track
from song_shift.providers.base import MusicProvider

FUZZY_THRESHOLD = 80


class TrackMatcher:
    """Match source tracks to a target provider using ISRC and fuzzy matching."""

    def match_track(
        self, source_track: Track, target_provider: MusicProvider
    ) -> MatchResult:
        """Match a single source track on the target provider.

        Strategy:
          1. If source has ISRC, try exact ISRC lookup.
          2. Fall back to fuzzy title+artist matching.
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

        # Fuzzy match (fallback)
        query = f"{source_track.title} {source_track.artist}"
        candidates = target_provider.search_track(query)

        source_str = f"{source_track.title} {source_track.artist}"
        best_match: Track | None = None
        best_score: float = 0.0

        for candidate in candidates:
            candidate_str = f"{candidate.title} {candidate.artist}"
            score = token_sort_ratio(source_str, candidate_str)
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
