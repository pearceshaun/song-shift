# YouTube Provider -- Project Guide

> Operational reference for this loop. Claude reads this each iteration to absorb
> project-specific patterns, commands, and conventions.
> **Behavioral instructions belong in `prompt.md`, not here.**

## Build & Test Commands

```bash
# Primary backpressure loop -- run after every change
uv run pytest tests/providers/test_youtube.py -v

# Full test suite -- run at milestones and before final push
uv run pytest -v

# Install dependencies after modifying pyproject.toml
uv sync
```

## Key Architectural Decisions (already made)

1. **yt-dlp is the only extraction tool** -- no YouTube Data API, no API keys
2. **Provider is source-only (read-only)** -- like ShazamProvider. `create_playlist()` and `add_tracks_to_playlist()` raise `NotImplementedError`
3. **Chapter title parsing uses simple string splitting** -- try ` - `, then `: `, then ` by `. Strip leading track numbers with regex `r'^\d+[\.\)\s]+\s*'`
4. **Description timestamp regex:** `r'(?:^|\s)(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)'`
5. **authenticate() is a no-op** -- public YouTube videos need no auth. `is_authenticated()` always returns True
6. **list_playlists() returns a single synthetic playlist** -- uses video title as name, URL as id
7. **search_track() returns []** and **search_track_by_isrc() returns None** -- YouTube has no catalog search in this provider
8. **Raw chapter/timestamp title is the fallback** -- if splitting fails, set artist="" and title=full string. The existing fuzzy matcher handles the rest
9. **Audio fingerprinting is NOT in scope** -- this is Phase 1 only
10. **Track.duration_ms** -- calculate from chapter end_time minus start_time (in seconds, convert to ms)
11. **Track.provider_id** -- use the video URL
12. **Track.provider** -- set to `"youtube"`
13. **Track.album** -- set to `""`
14. **Track.isrc** -- set to `None`
15. **yt-dlp usage** -- use `yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": False}).extract_info(url, download=False)`. The `download=False` flag prevents downloading the actual video.

## Codebase Patterns to Follow

### Read-only provider pattern
- **Pattern file:** `song_shift/providers/shazam.py`
- Class inherits from `MusicProvider`, decorated with `@register_provider`
- Constructor takes `credential_store: CredentialStore | None = None`
- Write methods raise `NotImplementedError("YouTube is a read-only source...")`
- `list_playlists()` returns a single synthetic `Playlist` object
- All Track objects use `provider="youtube"`, `album=""`, `isrc=None`

### Provider registration
- **Pattern file:** `song_shift/providers/__init__.py`
- Add `import song_shift.providers.youtube  # noqa: F401 -- register provider` to trigger registration

### Provider base class
- **Pattern file:** `song_shift/providers/base.py`
- Abstract methods: `authenticate`, `is_authenticated`, `list_playlists`, `get_playlist_tracks`, `search_track`, `search_track_by_isrc`, `create_playlist`, `add_tracks_to_playlist`

### Track model
- **Pattern file:** `song_shift/models.py` lines 5-16
- `Track(title, artist, album, provider_id, provider, isrc=None, duration_ms=None)`

### Testing
- **Framework:** pytest with `uv run pytest`
- **Mocking:** `unittest.mock` (patch, MagicMock)
- **Pattern file:** `tests/providers/test_shazam.py`
- Test classes grouped by concern: Authentication, Parsing, Search, ReadOnly
- Fixtures use `credential_store` from `tests/conftest.py`
- All external calls (yt-dlp) are mocked -- no real network calls
- Mock yt-dlp by patching `song_shift.providers.youtube.yt_dlp.YoutubeDL`
- Test file: `tests/providers/test_youtube.py`
- Naming: `test_<what_it_tests>` with descriptive docstrings

## Branch Info

- Working branch: `claude/youtube-provider-ralph-loop-2vxsm`
- Base branch: `claude/youtube-import-research-DDvWX`
- PR target: `main`
