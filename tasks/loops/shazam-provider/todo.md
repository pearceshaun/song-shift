# Shazam Provider -- Implementation Plan

Branch: `feature/shazam-provider`
Base: `main`
Spec: `tasks/loops/shazam-provider/specs/spec.md`

## Implementation Steps

### Phase 1: Scaffold and Dependencies

- [x] **1.1** Create feature branch `feature/shazam-provider` from `main`. Add `shazamio` to `pyproject.toml` dependencies. Add `import song_shift.providers.shazam` to `song_shift/providers/__init__.py`. Create `song_shift/providers/shazam.py` with the `ShazamProvider` class skeleton -- all 8 abstract methods stubbed with `raise NotImplementedError`. Decorate with `@register_provider`, set `name = "shazam"`. Ensure `python -m pytest` still passes (existing tests unaffected). Commit and push.

### Phase 2: CSV Authentication

- [x] **2.1** Implement `authenticate()` in `ShazamProvider`: accept a CSV file path (use `click.prompt` or `input()`), validate the file exists and has the required CSV headers (`Title`, `Artist`, `TrackKey`), store the path in `CredentialStore`. Implement `is_authenticated()`: check credentials exist AND file still exists on disk. Commit and push.

- [x] **2.2** Write tests for authentication in `tests/providers/test_shazam.py`: `TestShazamAuthentication` class with 6 test cases from the spec (test_authenticate_prompts_for_csv_path, test_authenticate_rejects_missing_file, test_authenticate_rejects_invalid_csv, test_is_authenticated_true_when_file_exists, test_is_authenticated_false_when_no_credentials, test_is_authenticated_false_when_file_deleted). Create helper to write temp CSV files. Run `python -m pytest` -- all pass. Commit and push.

### Phase 3: CSV Parsing (list_playlists + get_playlist_tracks)

- [x] **3.1** Implement `list_playlists()`: read CSV file, count rows, return single `Playlist(id="shazam-library", name="My Shazam Tracks", track_count=N, provider="shazam")`. Implement `get_playlist_tracks()`: parse CSV, map rows to `Track` objects (title from `Title`, artist from `Artist`, provider_id from `TrackKey`, provider="shazam", album="", isrc=None, duration_ms=None). Skip rows where Title AND Artist are both empty. Commit and push.

- [ ] **3.2** Write tests for CSV parsing in `tests/providers/test_shazam.py`: `TestShazamCSVParsing` class with 5 test cases from spec (test_list_playlists_returns_single_synthetic_playlist, test_get_playlist_tracks_parses_csv, test_get_playlist_tracks_skips_empty_rows, test_get_playlist_tracks_handles_missing_fields, test_get_playlist_tracks_sets_provider_fields). Run `python -m pytest` -- all pass. Commit and push.

### Phase 4: Search via shazamio

- [ ] **4.1** Implement `search_track()`: use `asyncio.run(Shazam().search_track(query, limit=5))`, map results to `Track` objects. Implement `search_track_by_isrc()`: return `None` (not supported). Ensure `create_playlist()` and `add_tracks_to_playlist()` raise `NotImplementedError` with message "Shazam is a read-only source and does not support playlist creation". Commit and push.

- [ ] **4.2** Write tests for search and read-only methods in `tests/providers/test_shazam.py`: `TestShazamSearch` class (test_search_track_returns_mapped_results, test_search_track_empty_results, test_search_track_by_isrc_returns_none) and `TestShazamReadOnly` class (test_create_playlist_raises_not_implemented, test_add_tracks_raises_not_implemented). Mock `shazamio.Shazam` for search tests. Run `python -m pytest` -- all pass. Commit and push.

### Phase 5: Final Verification

- [ ] **5.1** Run full test suite (`python -m pytest -v`). Verify all existing tests still pass. Verify Shazam provider is registered (can be checked by importing and calling `list_providers()`). Create PR targeting `main` using `gh pr create`. Commit and push any final fixes.

## Commit Strategy

1. Scaffold + dependencies + registration
2. Authentication implementation
3. Authentication tests
4. CSV parsing implementation
5. CSV parsing tests
6. Search + read-only implementation
7. Search + read-only tests
8. Final verification + PR

## Review Checklist

- [ ] ShazamProvider registered and appears in `list_providers()`
- [ ] CSV parsing handles edge cases (empty rows, missing columns)
- [ ] Search delegates to shazamio correctly
- [ ] Read-only methods raise NotImplementedError with clear message
- [ ] All 16 test cases from spec are implemented and passing
- [ ] Existing tests (tidal, apple_music, models, etc.) still pass
- [ ] PR created targeting main
