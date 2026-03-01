"""Playlist migration engine."""

from dataclasses import dataclass

from song_shift.matcher import TrackMatcher
from song_shift.models import MatchResult, Playlist
from song_shift.providers.base import MusicProvider


@dataclass
class MigrationReport:
    """Results of a playlist migration."""

    total_tracks: int
    matched_tracks: int
    unmatched_tracks: int
    isrc_matches: int
    fuzzy_matches: int
    created_playlist: Playlist
    match_results: list[MatchResult]

    def summary(self) -> str:
        """Return a human-readable summary of the migration."""
        return (
            f"Migrated {self.matched_tracks}/{self.total_tracks} tracks "
            f"({self.isrc_matches} ISRC, {self.fuzzy_matches} fuzzy, "
            f"{self.unmatched_tracks} unmatched) "
            f"to playlist '{self.created_playlist.name}'"
        )


class PlaylistMigrator:
    """Orchestrate playlist migration between providers."""

    def __init__(self) -> None:
        self.matcher = TrackMatcher()

    def migrate(
        self,
        source_provider: MusicProvider,
        playlist_id: str,
        target_provider: MusicProvider,
        playlist_name: str | None = None,
    ) -> MigrationReport:
        """Migrate a playlist from source to target provider.

        Args:
            source_provider: Provider to read the playlist from.
            playlist_id: ID of the playlist on the source provider.
            target_provider: Provider to create the playlist on.
            playlist_name: Custom name for the new playlist. If None, uses
                the source playlist's name.

        Returns:
            A MigrationReport with match results and counts.
        """
        # 1. Get source tracks
        source_tracks = source_provider.get_playlist_tracks(playlist_id)

        # Resolve playlist name from source if not provided
        if playlist_name is None:
            for playlist in source_provider.list_playlists():
                if playlist.id == playlist_id:
                    playlist_name = playlist.name
                    break
            else:
                playlist_name = "Migrated Playlist"

        # 2. Match tracks
        match_results = self.matcher.match_tracks(source_tracks, target_provider)

        # 3. Filter matched tracks
        matched = [r for r in match_results if r.method != "none"]
        matched_track_ids = [r.matched_track.provider_id for r in matched]

        # 4. Create playlist on target
        new_playlist = target_provider.create_playlist(playlist_name, "")

        # 5. Add matched tracks
        if matched_track_ids:
            target_provider.add_tracks_to_playlist(new_playlist.id, matched_track_ids)

        # 6. Compute counts
        isrc_matches = sum(1 for r in match_results if r.method == "isrc")
        fuzzy_matches = sum(1 for r in match_results if r.method == "fuzzy")

        return MigrationReport(
            total_tracks=len(source_tracks),
            matched_tracks=len(matched),
            unmatched_tracks=len(source_tracks) - len(matched),
            isrc_matches=isrc_matches,
            fuzzy_matches=fuzzy_matches,
            created_playlist=new_playlist,
            match_results=match_results,
        )
