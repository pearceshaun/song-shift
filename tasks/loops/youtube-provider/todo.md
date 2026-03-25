# YouTube Provider -- Implementation Plan

Branch: `claude/youtube-provider-ralph-loop-2vxsm`
Base: `claude/youtube-import-research-DDvWX`
Spec: `tasks/loops/youtube-provider/specs/spec.md`

## Implementation Steps

### Phase 1: Foundation

- [ ] **1.1** Add `yt-dlp` to `pyproject.toml` dependencies and run `uv sync` to install
- [ ] **1.2** Create `song_shift/providers/youtube.py` with `YouTubeProvider` class skeleton (all methods raising NotImplementedError or returning empty), register it in `song_shift/providers/__init__.py`
- [ ] **1.3** Implement `_parse_chapter_title(title)` helper function with delimiter splitting logic (` - `, `: `, ` by `) and track number stripping

### Phase 2: Core Provider Logic

- [ ] **2.1** Implement `_parse_description_timestamps(description)` helper function with regex timestamp parsing
- [ ] **2.2** Implement `get_playlist_tracks(playlist_id)` -- call yt-dlp `extract_info`, parse chapters into Track objects, fall back to description parsing
- [ ] **2.3** Implement `list_playlists(playlist_id_url)`, `authenticate()`, `is_authenticated()`, `search_track()`, `search_track_by_isrc()` -- simple methods following Shazam pattern

### Phase 3: Tests

- [ ] **3.1** Write `tests/providers/test_youtube.py` -- TestYouTubeAuthentication (3 tests) and TestYouTubeReadOnly (2 tests)
- [ ] **3.2** Write TestYouTubeChapterParsing (5 tests) and TestYouTubePlaylistMetadata (3 tests)
- [ ] **3.3** Write TestYouTubeDescriptionFallback (3 tests) and TestYouTubeEdgeCases (3 tests)

### Phase 4: Verification

- [ ] **4.1** Run full test suite (`uv run pytest`), fix any regressions or failures across all tests
- [ ] **4.2** Review all YouTube provider code for consistency with Shazam provider patterns and spec compliance

## Commit Strategy

1. Phase 1: Add yt-dlp dependency + provider skeleton + title parser
2. Phase 2: Core provider logic (yt-dlp integration, description parsing)
3. Phase 3: Full test suite (19 tests)
4. Phase 4: Any fixups from test runs

## Review Checklist

- [ ] `yt-dlp` added to pyproject.toml and installs cleanly
- [ ] YouTubeProvider registered and appears in `list_providers()`
- [ ] Chapter parsing correctly splits "Artist - Title", "Artist: Title", "Title by Artist"
- [ ] Description timestamp fallback works when chapters absent
- [ ] Write methods raise NotImplementedError with "read-only" message
- [ ] All 19 YouTube tests pass
- [ ] Existing tests still pass (no regressions)
