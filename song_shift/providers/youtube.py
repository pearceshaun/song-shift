"""YouTube provider using yt-dlp to extract tracks from video chapters/descriptions."""

import re

import yt_dlp

from song_shift.models import Playlist, Track
from song_shift.providers.base import MusicProvider, register_provider


def _parse_chapter_title(title: str) -> tuple[str, str]:
    """Parse a chapter title into (artist, title).

    Tries splitting on ' - ', ': ', and ' by ' (case-insensitive).
    Strips leading track numbers like '1. ' or '2) '.
    Returns (artist, title) or ('', cleaned_title) if no delimiter found.
    """
    cleaned = re.sub(r"^\d+[\.\)\s]+\s*", "", title)

    if " - " in cleaned:
        parts = cleaned.split(" - ", 1)
        return parts[0].strip(), parts[1].strip()

    if ": " in cleaned:
        parts = cleaned.split(": ", 1)
        return parts[0].strip(), parts[1].strip()

    match = re.split(r"\s+by\s+", cleaned, maxsplit=1, flags=re.IGNORECASE)
    if len(match) == 2:
        return match[1].strip(), match[0].strip()

    return "", cleaned.strip()


def _parse_description_timestamps(description: str) -> list[tuple[str, str]]:
    """Parse description lines for timestamp entries.

    Matches lines like '0:00 Artist - Song Title' or '1:23:45 Some Track'.
    Returns list of (artist, title) tuples.
    """
    results = []
    pattern = re.compile(r"(?:^|\s)(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)")
    for line in description.splitlines():
        m = pattern.match(line.strip())
        if m:
            track_text = m.group(2).strip()
            artist, title = _parse_chapter_title(track_text)
            results.append((artist, title))
    return results


@register_provider
class YouTubeProvider(MusicProvider):
    """Read-only YouTube provider that extracts tracks from video metadata."""

    name = "youtube"

    def authenticate(self) -> None:
        """No authentication needed for public YouTube videos."""

    def is_authenticated(self) -> bool:
        """Always returns True -- no credentials required."""
        return True

    def list_playlists(self, url: str | None = None) -> list[Playlist]:
        """Return a single synthetic playlist from the video title."""
        if not url:
            return []
        ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        video_title = info.get("title", "YouTube Video")
        tracks = self._extract_tracks(info)
        return [
            Playlist(
                id=url,
                name=video_title,
                track_count=len(tracks),
                provider="youtube",
            )
        ]

    def get_playlist_tracks(self, playlist_id: str) -> list[Track]:
        """Extract tracks from a YouTube video's chapters or description."""
        ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_id, download=False)
        return self._extract_tracks(info)

    def _extract_tracks(self, info: dict) -> list[Track]:
        """Extract Track objects from yt-dlp info dict.

        Uses the video uploader/channel name as a fallback artist when
        chapter titles don't contain an artist delimiter.
        """
        fallback_artist = (
            info.get("artist")
            or info.get("uploader")
            or info.get("channel")
            or ""
        )
        chapters = info.get("chapters") or []
        if chapters:
            return self._tracks_from_chapters(chapters, fallback_artist)
        description = info.get("description") or ""
        return self._tracks_from_description(description, fallback_artist)

    def _tracks_from_chapters(
        self, chapters: list[dict], fallback_artist: str = ""
    ) -> list[Track]:
        """Convert chapter entries to Track objects."""
        tracks = []
        for chapter in chapters:
            raw_title = chapter.get("title", "")
            start = chapter.get("start_time", 0)
            end = chapter.get("end_time", 0)
            duration_ms = int((end - start) * 1000) if end > start else None
            artist, title = _parse_chapter_title(raw_title)
            if not artist:
                artist = fallback_artist
            tracks.append(
                Track(
                    title=title,
                    artist=artist,
                    album="",
                    provider_id=raw_title,
                    provider="youtube",
                    isrc=None,
                    duration_ms=duration_ms,
                )
            )
        return tracks

    def _tracks_from_description(
        self, description: str, fallback_artist: str = ""
    ) -> list[Track]:
        """Parse description timestamps into Track objects."""
        parsed = _parse_description_timestamps(description)
        return [
            Track(
                title=title,
                artist=artist or fallback_artist,
                album="",
                provider_id=f"{artist} - {title}" if artist else title,
                provider="youtube",
                isrc=None,
                duration_ms=None,
            )
            for artist, title in parsed
        ]

    def search_track(self, query: str) -> list[Track]:
        """Not supported -- YouTube is source-only."""
        return []

    def search_track_by_isrc(self, isrc: str) -> Track | None:
        """Not supported -- YouTube is source-only."""
        return None

    def create_playlist(self, name: str, description: str) -> Playlist:
        """Not supported -- YouTube is a read-only source."""
        raise NotImplementedError(
            "YouTube is a read-only source and does not support playlist creation"
        )

    def add_tracks_to_playlist(self, playlist_id: str, track_ids: list[str]) -> int:
        """Not supported -- YouTube is a read-only source."""
        raise NotImplementedError(
            "YouTube is a read-only source and does not support adding tracks"
        )
