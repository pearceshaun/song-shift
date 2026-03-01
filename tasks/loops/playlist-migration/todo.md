# Playlist Migration — Implementation Plan

Branch: `claude/playlist-migration-plan-SfdvN`
Base: `claude/playlist-migration-plan-SfdvN`
Spec: `tasks/loops/playlist-migration/specs/spec.md`

## Implementation Steps

### Phase 1: Project Scaffolding

- [x] **1.1** Create project skeleton — `pyproject.toml` (with click, httpx, tidalapi, PyJWT, rapidfuzz, pytest, pytest-httpx dependencies), `.gitignore` (Python template), `.env.example`, and all `__init__.py` files for `song_shift/`, `song_shift/providers/`, `tests/`, `tests/providers/`. Add `song_shift/__main__.py`. Run `uv sync` to install dependencies.
- [x] **1.2** Create `song_shift/models.py` — Track, Playlist, MatchResult dataclasses per spec. Write `tests/test_models.py` with all 6 test cases from spec. Run `uv run pytest tests/test_models.py` — all pass.

### Phase 2: Provider Foundation

- [x] **2.1** Create `song_shift/config.py` — CredentialStore class per spec. Write `tests/test_config.py` with all 6 test cases from spec (use tmp_path fixture for isolation). Run `uv run pytest tests/test_config.py` — all pass.
- [x] **2.2** Create `song_shift/providers/base.py` — MusicProvider ABC with all required abstract methods per spec. Add provider registry (register/get/list functions). Write `tests/test_provider_base.py` with all 4 test cases from spec. Run `uv run pytest tests/test_provider_base.py` — all pass.

### Phase 3: Tidal Provider

- [x] **3.1** Create `song_shift/providers/tidal.py` — TidalProvider implementing MusicProvider. All methods per spec: authenticate (OAuth device code), is_authenticated, list_playlists, get_playlist_tracks, search_track, search_track_by_isrc, create_playlist, add_tracks_to_playlist. Register with provider registry.
- [x] **3.2** Write `tests/providers/test_tidal.py` — all 10 test cases from spec. Mock `tidalapi.Session` and related objects. Run `uv run pytest tests/providers/test_tidal.py` — all pass.

### Phase 4: Apple Music Provider

- [x] **4.1** Create `song_shift/providers/apple_music.py` — AppleMusicProvider implementing MusicProvider. JWT developer token generation, all API methods per spec with pagination support. Register with provider registry.
- [x] **4.2** Write `tests/providers/test_apple_music.py` — all 11 test cases from spec. Mock httpx responses. Run `uv run pytest tests/providers/test_apple_music.py` — all pass.

### Phase 5: Track Matching

- [x] **5.1** Create `song_shift/matcher.py` — TrackMatcher with ISRC primary + fuzzy fallback per spec. Write `tests/test_matcher.py` with all 7 test cases from spec. Run `uv run pytest tests/test_matcher.py` — all pass.

### Phase 6: Migration Engine

- [x] **6.1** Create `song_shift/migrator.py` — PlaylistMigrator + MigrationReport per spec. Write `tests/test_migrator.py` with all 7 test cases from spec. Run `uv run pytest tests/test_migrator.py` — all pass.

### Phase 7: CLI

- [x] **7.1** Create `song_shift/cli.py` — Click CLI group with `auth` and `list` commands per spec. Update `song_shift/providers/__init__.py` to register all providers on import. Verify `uv run python -m song_shift --help` shows commands.
- [x] **7.2** Add `migrate` command to `song_shift/cli.py` — with `--playlist-id`, `--playlist-name`, and `--dry-run` options per spec. Write `tests/test_cli.py` with all 7 test cases from spec using Click's CliRunner. Run `uv run pytest tests/test_cli.py` — all pass.

### Phase 8: Integration & Verification

- [x] **8.1** Create `tests/conftest.py` with shared fixtures (mock providers, sample tracks, sample playlists). Run `uv run pytest` (full suite) — all tests pass. Fix any regressions.
- [x] **8.2** Final verification — run full test suite, verify `song-shift --help`, `song-shift auth --help`, `song-shift list --help`, `song-shift migrate --help` all work. Verify test count matches spec expectations (~68 tests total). *(Verified: 58 tests all passing, all CLI commands working.)*

## Commit Strategy

1. Phase 1: Project scaffolding + models + tests
2. Phase 2: Config + provider base + tests
3. Phase 3: Tidal provider + tests
4. Phase 4: Apple Music provider + tests
5. Phase 5: Matcher + tests
6. Phase 6: Migrator + tests
7. Phase 7: CLI + tests
8. Phase 8: Shared fixtures + final fixes

## Review Checklist

- [ ] All 68+ unit tests pass
- [ ] `song-shift auth tidal` runs the OAuth device code flow
- [ ] `song-shift list tidal` shows playlists (when authenticated)
- [ ] `song-shift migrate apple_music tidal --playlist-id X` runs full pipeline
- [ ] `--dry-run` flag shows match results without creating playlist
- [ ] Credentials stored securely in ~/.config/song-shift/
- [ ] No hardcoded secrets or API keys in source code
- [ ] Provider architecture is extensible (easy to add Spotify later)
