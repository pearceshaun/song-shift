# YouTube Provider -- Technical Specification

## Problem Statement

song-shift can import from Apple Music, Tidal, and Shazam but cannot import from
YouTube. Many users have YouTube videos (DJ mixes, compilations, "best of" playlists)
with timestamped track lists they want to migrate to streaming services.

## Proposed Solution

Add a read-only `YouTubeProvider` that uses yt-dlp to extract video metadata and
parse chapter titles or description timestamps into `Track` objects. This follows
the same source-only pattern as `ShazamProvider`.

## Components

### YouTubeProvider

- **File:** `song_shift/providers/youtube.py`
- **Responsibility:** Extract tracks from YouTube video metadata (chapters or description timestamps)
- **Dependencies:** `yt-dlp` (metadata extraction), `song_shift.models.Track`, `song_shift.providers.base`

### Track title parser (internal functions)

- **File:** `song_shift/providers/youtube.py` (module-level helper functions)
- **Responsibility:** Parse chapter titles like "Artist - Title" into separate artist/title fields
- **Dependencies:** `re` (standard library)

## Data Flow

1. User runs `song-shift migrate youtube tidal --playlist-id "https://youtu.be/xxx"`
2. CLI calls `YouTubeProvider.get_playlist_tracks(url)`
3. Provider calls `yt_dlp.YoutubeDL.extract_info(url, download=False)`
4. If `info["chapters"]` exists: parse each chapter title into a Track
5. If no chapters: parse description for timestamp lines using regex
6. Return list of Track objects
7. Existing TrackMatcher matches tracks against target service
8. PlaylistMigrator creates playlist on target

## Configuration

No env vars required. yt-dlp works without API keys for public videos.

## Existing Code References

- **Read-only provider pattern:** See `song_shift/providers/shazam.py` -- entire file is the template
- **Provider registration:** See `song_shift/providers/base.py` lines 1-30 for `@register_provider`
- **Provider imports:** See `song_shift/providers/__init__.py` -- add YouTube import here
- **Track model:** See `song_shift/models.py` lines 5-16 for Track dataclass
- **Test pattern:** See `tests/providers/test_shazam.py` -- mirror structure for YouTube tests

## Key Architectural Decisions (locked in)

1. **yt-dlp is the only extraction tool** -- no YouTube Data API, no API keys needed
2. **Provider is source-only** -- `create_playlist` and `add_tracks_to_playlist` raise `NotImplementedError`
3. **Chapter titles are parsed with simple heuristics** -- split on ` - `, `: `, ` by `; strip track numbers. No ML or complex NLP.
4. **Raw title is always set as the search query fallback** -- since the existing fuzzy matcher handles imperfect queries well
5. **Description timestamp regex:** `r'(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)'` for lines like `0:00 Artist - Song Title`
6. **authenticate() stores nothing** -- YouTube public videos need no credentials. Provider is always "authenticated".
7. **list_playlists() returns a single synthetic playlist** -- similar to Shazam's approach, using video title as playlist name
8. **search_track() and search_track_by_isrc() return empty/None** -- YouTube is source-only, no catalog search
9. **Audio fingerprinting is NOT included** -- deferred to a future phase

## Track Title Parsing Logic

The `_parse_chapter_title(title: str)` function:

1. Strip leading track numbers: `re.sub(r'^\d+[\.\)\s]+\s*', '', title)`
2. Try splitting on ` - ` (most common): `parts = title.split(" - ", 1)`
3. Try splitting on `: ` if no dash: `parts = title.split(": ", 1)`
4. Try splitting on ` by ` (case-insensitive) if no colon
5. If split succeeded (2 parts): `artist = parts[0].strip()`, `title = parts[1].strip()`
6. If no split: `artist = ""`, `title = cleaned_title.strip()`

Return a tuple `(artist, title)`.

## Description Timestamp Parsing Logic

The `_parse_description_timestamps(description: str)` function:

1. Split description into lines
2. For each line, try matching `r'(?:^|\s)(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)'`
3. Collect matches as list of `(timestamp_str, track_title_str)`
4. Parse each track title through `_parse_chapter_title()`
5. Return list of `(artist, title)` tuples

## Test Cases

### Unit Tests

**File:** `tests/providers/test_youtube.py`

#### TestYouTubeAuthentication (3 tests)

1. `test_authenticate_succeeds_silently` -- authenticate() does not raise; no credentials stored
2. `test_is_authenticated_always_true` -- is_authenticated() returns True (no auth needed for public videos)
3. `test_search_track_by_isrc_returns_none` -- search_track_by_isrc() returns None

#### TestYouTubeChapterParsing (5 tests)

4. `test_get_tracks_from_chapters` -- Given video info with chapters list, returns Track objects with correct artist/title parsed from "Artist - Title" format
5. `test_get_tracks_strips_track_numbers` -- Chapter titles like "1. Artist - Title" have number stripped
6. `test_get_tracks_colon_separator` -- Chapter titles like "Artist: Title" are split correctly
7. `test_get_tracks_by_separator` -- Chapter titles like "Title by Artist" are split correctly (artist/title swapped)
8. `test_get_tracks_no_separator_uses_raw_title` -- Chapter titles with no delimiter set artist="" and title=full string

#### TestYouTubeDescriptionFallback (3 tests)

9. `test_get_tracks_falls_back_to_description` -- When chapters absent, parses description timestamps
10. `test_description_handles_hhmmss_format` -- Timestamps like "1:23:45 Artist - Title" are parsed
11. `test_description_ignores_non_timestamp_lines` -- Lines without timestamps are skipped

#### TestYouTubePlaylistMetadata (3 tests)

12. `test_list_playlists_returns_synthetic_playlist` -- Returns single Playlist with video title as name
13. `test_get_playlist_tracks_uses_url_as_id` -- playlist_id parameter is passed to yt-dlp as the URL
14. `test_tracks_have_youtube_provider_fields` -- provider="youtube", album="", isrc=None, duration_ms set from chapter duration

#### TestYouTubeReadOnly (2 tests)

15. `test_create_playlist_raises_not_implemented` -- Raises NotImplementedError with "read-only" in message
16. `test_add_tracks_raises_not_implemented` -- Raises NotImplementedError with "read-only" in message

#### TestYouTubeEdgeCases (3 tests)

17. `test_empty_chapters_falls_back_to_description` -- Empty chapters list triggers description parsing
18. `test_no_chapters_no_description_returns_empty` -- Video with no chapters and no timestamps returns []
19. `test_search_track_returns_empty_list` -- search_track() returns [] (no YouTube catalog search)

**Total: 19 test cases**

## Files Changed

### New Files
- `song_shift/providers/youtube.py` -- YouTubeProvider class and helper functions
- `tests/providers/test_youtube.py` -- 19 unit tests

### Modified Files
- `pyproject.toml` -- Add `yt-dlp` to dependencies
- `song_shift/providers/__init__.py` -- Add YouTube provider import
