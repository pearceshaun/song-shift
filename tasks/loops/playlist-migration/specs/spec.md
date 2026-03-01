# Playlist Migration — Technical Specification

## Problem Statement

Users with music libraries spread across Apple Music and Tidal have no simple way to transfer playlists between services. Existing tools are web-based, require accounts, and often break when APIs change. We need a local CLI tool that reads playlists from one service, matches tracks on the target service, and creates the playlist there — with clear reporting on what matched and what didn't.

## Proposed Solution

A Python CLI tool (`song-shift`) that implements a provider-based architecture. Each music service is a provider conforming to an abstract interface. A matching engine resolves tracks across services using ISRC codes (primary) and fuzzy title/artist matching (fallback). A migration engine orchestrates the full flow: read → match → write.

## Components

### Track / Playlist / MatchResult Models
- **File:** `song_shift/models.py`
- **Responsibility:** Core data classes shared across all components. Track holds title, artist, album, ISRC, duration, and provider-specific ID. Playlist holds name, description, and list of Tracks. MatchResult holds source track, matched track (or None), match method (isrc/fuzzy/none), and confidence score.
- **Dependencies:** None (stdlib dataclasses only)

### MusicProvider ABC
- **File:** `song_shift/providers/base.py`
- **Responsibility:** Abstract base class defining the provider contract. Also contains a provider registry for discovering available providers by name.
- **Dependencies:** `abc` module, `song_shift.models`
- **Required methods:**
  - `name` (property) → str — provider identifier (e.g. "apple_music", "tidal")
  - `authenticate()` → None — run interactive auth flow, store credentials
  - `is_authenticated()` → bool — check if valid credentials exist
  - `list_playlists()` → list[Playlist] — return user's playlists (metadata only, no tracks)
  - `get_playlist_tracks(playlist_id: str)` → list[Track] — return tracks in a playlist
  - `search_track(query: str)` → list[Track] — search the catalog
  - `search_track_by_isrc(isrc: str)` → Track | None — exact ISRC lookup
  - `create_playlist(name: str, description: str)` → Playlist — create empty playlist
  - `add_tracks_to_playlist(playlist_id: str, track_ids: list[str])` → int — add tracks, return count added

### CredentialStore
- **File:** `song_shift/config.py`
- **Responsibility:** Persist and retrieve provider credentials. Stores JSON in `~/.config/song-shift/credentials.json`. Handles file creation, read, write, and per-provider key management.
- **Dependencies:** `pathlib`, `json`
- **Methods:**
  - `get(provider: str)` → dict | None
  - `save(provider: str, credentials: dict)` → None
  - `delete(provider: str)` → None
  - `list_providers()` → list[str] — return names of providers with saved credentials

### TidalProvider
- **File:** `song_shift/providers/tidal.py`
- **Responsibility:** Tidal integration using the `tidalapi` package.
- **Dependencies:** `tidalapi`, `song_shift.providers.base`, `song_shift.models`, `song_shift.config`
- **Auth flow:** OAuth2 device code flow via `tidalapi.Session.login_oauth_simple()`. Stores OAuth token data (token_type, access_token, refresh_token, expiry) in CredentialStore. On subsequent runs, loads stored token and calls `session.load_oauth_session()`.
- **Track mapping:** Map `tidalapi.Track` → `song_shift.models.Track` with fields: title=track.name, artist=track.artist.name, album=track.album.name, isrc=track.isrc, duration_ms=track.duration*1000, provider_id=str(track.id), provider="tidal"
- **Playlist mapping:** Map `tidalapi.Playlist` → `song_shift.models.Playlist` with fields: id=str(playlist.id), name=playlist.name, description=playlist.description or "", track_count=playlist.num_tracks, provider="tidal"

### AppleMusicProvider
- **File:** `song_shift/providers/apple_music.py`
- **Responsibility:** Apple Music integration using the MusicKit REST API via httpx.
- **Dependencies:** `httpx`, `jwt` (PyJWT), `song_shift.providers.base`, `song_shift.models`, `song_shift.config`
- **Auth flow — Developer Token:** Generate JWT signed with ES256 using: team_id, key_id, and private_key_path (path to .p8 file from Apple Developer Portal). Token valid for 6 months max. User provides these via `auth` command prompts.
- **Auth flow — Music User Token:** User must provide a Music User Token (MUT) obtained through Apple's web auth flow. The CLI prompts for this token. Stored in CredentialStore.
- **API base URL:** `https://api.music.apple.com/v1/`
- **Headers:** `Authorization: Bearer {developer_token}`, `Music-User-Token: {user_token}`
- **Endpoints used:**
  - `GET /v1/me/library/playlists` — list playlists
  - `GET /v1/me/library/playlists/{id}/tracks` — get tracks in a playlist
  - `POST /v1/me/library/playlists` — create playlist
  - `POST /v1/me/library/playlists/{id}/tracks` — add tracks
  - `GET /v1/catalog/{storefront}/search?types=songs&term={query}` — search
  - `GET /v1/catalog/{storefront}/songs?filter[isrc]={isrc}` — ISRC lookup
- **Storefront:** Stored as part of credentials. Default prompt to user during auth. Common: "gb", "us".
- **Track mapping:** API song object → Track: title=attributes.name, artist=attributes.artistName, album=attributes.albumName, isrc=attributes.isrc, duration_ms=attributes.durationInMillis, provider_id=id, provider="apple_music"
- **Pagination:** Apple Music API uses `next` URLs for pagination. All list methods must follow pagination links to get complete results, up to a reasonable limit (500 tracks max).

### TrackMatcher
- **File:** `song_shift/matcher.py`
- **Responsibility:** Match source tracks to target service tracks.
- **Dependencies:** `rapidfuzz`, `song_shift.models`, `song_shift.providers.base`
- **Strategy:**
  1. **ISRC match (primary):** If source track has an ISRC, call `target_provider.search_track_by_isrc(isrc)`. If found, return MatchResult with method="isrc", confidence=1.0.
  2. **Fuzzy match (fallback):** Build query string `"{title} {artist}"`, call `target_provider.search_track(query)`. Score each result using `rapidfuzz.fuzz.token_sort_ratio` on `"{title} {artist}"` for both source and candidate. Accept best match if score >= 80. Return MatchResult with method="fuzzy", confidence=score/100.
  3. **No match:** Return MatchResult with matched_track=None, method="none", confidence=0.0.
- **Methods:**
  - `match_track(source_track: Track, target_provider: MusicProvider)` → MatchResult
  - `match_tracks(source_tracks: list[Track], target_provider: MusicProvider, on_progress: Callback | None)` → list[MatchResult] — match all, calling on_progress after each

### PlaylistMigrator
- **File:** `song_shift/migrator.py`
- **Responsibility:** Orchestrate the full migration pipeline.
- **Dependencies:** `song_shift.matcher`, `song_shift.providers.base`, `song_shift.models`
- **Flow:**
  1. Call `source_provider.get_playlist_tracks(playlist_id)` → source_tracks
  2. Call `matcher.match_tracks(source_tracks, target_provider)` → match_results
  3. Filter matched tracks (method != "none")
  4. Call `target_provider.create_playlist(name, description)` → new_playlist
  5. Call `target_provider.add_tracks_to_playlist(new_playlist.id, matched_track_ids)` → count
  6. Return MigrationReport(total, matched, unmatched, created_playlist, match_results)
- **Methods:**
  - `migrate(source_provider, playlist_id, target_provider, playlist_name=None)` → MigrationReport
- **MigrationReport** (dataclass in this file):
  - total_tracks: int
  - matched_tracks: int
  - unmatched_tracks: int
  - isrc_matches: int
  - fuzzy_matches: int
  - created_playlist: Playlist
  - match_results: list[MatchResult]
  - `summary()` → str — human-readable summary

### CLI
- **File:** `song_shift/cli.py`
- **Responsibility:** Click-based CLI with commands: auth, list, migrate.
- **Dependencies:** `click`, `song_shift.providers`, `song_shift.migrator`, `song_shift.config`
- **Commands:**
  - `song-shift auth <provider>` — run interactive auth for a provider
  - `song-shift list <provider>` — list playlists from a provider
  - `song-shift migrate <source> <target> --playlist-id <id>` — migrate a playlist
    - Optional: `--playlist-name <name>` — custom name for created playlist
    - Optional: `--dry-run` — show match results without creating playlist
- **Output:** Use `click.echo` and `click.style` for colored output. Show progress with click.progressbar during matching.

### Entry Point
- **File:** `song_shift/__main__.py`
- **Responsibility:** Allow `python -m song_shift` execution.
- **Contents:** `from song_shift.cli import cli; cli()`

## Data Flow

1. User runs `song-shift migrate apple_music tidal --playlist-id p.abc123`
2. CLI resolves source/target providers from registry, checks both are authenticated
3. CLI creates PlaylistMigrator with TrackMatcher
4. Migrator calls `source_provider.get_playlist_tracks("p.abc123")` → list of Tracks
5. Migrator calls `matcher.match_tracks(tracks, target_provider)` → list of MatchResults
6. Migrator filters to successful matches, extracts target provider_ids
7. Migrator calls `target_provider.create_playlist(name, description)`
8. Migrator calls `target_provider.add_tracks_to_playlist(new_id, track_ids)`
9. Migrator builds MigrationReport and returns to CLI
10. CLI prints summary: X/Y tracks matched (N via ISRC, M via fuzzy), Z unmatched

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `SONG_SHIFT_CONFIG_DIR` | `~/.config/song-shift` | Directory for credentials and config |
| `APPLE_MUSIC_KEY_PATH` | None | Path to Apple Music .p8 private key file |
| `APPLE_MUSIC_KEY_ID` | None | Apple Music key ID from developer portal |
| `APPLE_MUSIC_TEAM_ID` | None | Apple Developer team ID |
| `APPLE_MUSIC_STOREFRONT` | `gb` | Apple Music storefront code |

## Test Cases

### Unit Tests — Models

**File:** `tests/test_models.py`

1. `test_track_creation` — Track dataclass holds all fields correctly
2. `test_track_equality` — Two tracks with same provider_id and provider are equal
3. `test_playlist_creation` — Playlist dataclass holds all fields, tracks defaults to empty list
4. `test_match_result_creation` — MatchResult holds source, matched track, method, and confidence
5. `test_match_result_is_matched` — is_matched property returns True when matched_track is not None
6. `test_track_display_str` — str(track) returns "artist - title"

### Unit Tests — Config

**File:** `tests/test_config.py`

1. `test_save_and_get_credentials` — save credentials, then get returns them
2. `test_get_nonexistent_provider` — returns None for unknown provider
3. `test_delete_credentials` — save, delete, then get returns None
4. `test_list_providers` — returns list of provider names with saved credentials
5. `test_creates_config_directory` — config directory is created if it doesn't exist
6. `test_credentials_file_permissions` — credentials file is not world-readable (mode 600)

### Unit Tests — Provider Base

**File:** `tests/test_provider_base.py`

1. `test_cannot_instantiate_abstract` — MusicProvider cannot be instantiated directly
2. `test_register_and_get_provider` — register a provider class, retrieve by name
3. `test_get_unknown_provider` — returns None for unregistered name
4. `test_list_registered_providers` — returns list of registered provider names

### Unit Tests — Tidal Provider

**File:** `tests/providers/test_tidal.py`

1. `test_authenticate_starts_oauth_flow` — authenticate() calls tidalapi login_oauth_simple
2. `test_authenticate_stores_credentials` — after auth, credentials are saved to CredentialStore
3. `test_is_authenticated_with_valid_token` — returns True when stored token loads successfully
4. `test_is_authenticated_without_credentials` — returns False when no credentials stored
5. `test_list_playlists_returns_mapped_playlists` — maps tidalapi Playlist objects to our Playlist model
6. `test_get_playlist_tracks_returns_mapped_tracks` — maps tidalapi Track objects to our Track model with ISRC
7. `test_search_track_by_isrc` — searches Tidal catalog by ISRC, returns mapped Track
8. `test_search_track` — searches by query string, returns list of mapped Tracks
9. `test_create_playlist` — creates playlist via tidalapi, returns mapped Playlist
10. `test_add_tracks_to_playlist` — adds tracks by ID, returns count added

### Unit Tests — Apple Music Provider

**File:** `tests/providers/test_apple_music.py`

1. `test_generate_developer_token` — generates valid JWT with correct claims and ES256 signing
2. `test_authenticate_stores_credentials` — stores all auth components in CredentialStore
3. `test_is_authenticated_with_valid_credentials` — returns True when all credentials present
4. `test_is_authenticated_with_missing_credentials` — returns False when credentials incomplete
5. `test_list_playlists` — calls API, handles pagination, returns mapped Playlists
6. `test_get_playlist_tracks` — calls API, handles pagination, returns mapped Tracks with ISRC
7. `test_search_track_by_isrc` — calls ISRC filter endpoint, returns Track or None
8. `test_search_track` — calls search endpoint, returns list of mapped Tracks
9. `test_create_playlist` — POSTs to API, returns mapped Playlist
10. `test_add_tracks_to_playlist` — POSTs track IDs, returns count
11. `test_api_error_handling` — raises appropriate exceptions on 401, 403, 429 responses

### Unit Tests — Matcher

**File:** `tests/test_matcher.py`

1. `test_isrc_match_found` — track with ISRC matches via provider.search_track_by_isrc, confidence=1.0
2. `test_isrc_match_not_found_falls_back_to_fuzzy` — ISRC returns None, fuzzy search finds match
3. `test_fuzzy_match_above_threshold` — fuzzy score >= 80 returns match with method="fuzzy"
4. `test_fuzzy_match_below_threshold` — fuzzy score < 80 returns no match, method="none"
5. `test_no_isrc_goes_straight_to_fuzzy` — track without ISRC skips ISRC lookup
6. `test_match_tracks_processes_all` — match_tracks returns MatchResult for every input track
7. `test_match_tracks_calls_progress_callback` — on_progress called once per track

### Unit Tests — Migrator

**File:** `tests/test_migrator.py`

1. `test_migrate_full_flow` — reads tracks, matches, creates playlist, adds matched tracks
2. `test_migrate_report_counts` — report has correct total, matched, unmatched, isrc, fuzzy counts
3. `test_migrate_with_unmatched_tracks` — unmatched tracks excluded from created playlist
4. `test_migrate_custom_playlist_name` — uses custom name when provided
5. `test_migrate_uses_source_name_by_default` — uses source playlist name when no custom name given
6. `test_migrate_report_summary` — summary() returns human-readable string with counts
7. `test_migrate_empty_playlist` — handles playlist with zero tracks gracefully

### Unit Tests — CLI

**File:** `tests/test_cli.py`

1. `test_auth_command_runs_provider_auth` — `auth tidal` calls TidalProvider.authenticate()
2. `test_auth_unknown_provider` — shows error for unregistered provider
3. `test_list_command_shows_playlists` — `list tidal` displays playlist names and track counts
4. `test_list_unauthenticated_provider` — shows error when provider not authenticated
5. `test_migrate_command_runs_migration` — `migrate apple_music tidal --playlist-id X` runs full flow
6. `test_migrate_dry_run` — `--dry-run` shows match results without creating playlist
7. `test_migrate_shows_summary` — output includes match counts and unmatched tracks

## Files Changed

### New Files
- `pyproject.toml` — Project metadata, dependencies, CLI entry point
- `.gitignore` — Python gitignore
- `.env.example` — Example environment variables
- `song_shift/__init__.py` — Package init with version
- `song_shift/__main__.py` — Entry point for `python -m song_shift`
- `song_shift/models.py` — Track, Playlist, MatchResult dataclasses
- `song_shift/config.py` — CredentialStore for persisting auth tokens
- `song_shift/providers/__init__.py` — Provider package init, registers all providers
- `song_shift/providers/base.py` — MusicProvider ABC + registry
- `song_shift/providers/tidal.py` — TidalProvider
- `song_shift/providers/apple_music.py` — AppleMusicProvider
- `song_shift/matcher.py` — TrackMatcher
- `song_shift/migrator.py` — PlaylistMigrator + MigrationReport
- `song_shift/cli.py` — Click CLI with auth, list, migrate commands
- `tests/__init__.py` — Test package init
- `tests/conftest.py` — Shared pytest fixtures
- `tests/test_models.py` — Model unit tests
- `tests/test_config.py` — Config unit tests
- `tests/test_provider_base.py` — Provider base unit tests
- `tests/providers/__init__.py` — Provider test package init
- `tests/providers/test_tidal.py` — Tidal provider unit tests
- `tests/providers/test_apple_music.py` — Apple Music provider unit tests
- `tests/test_matcher.py` — Matcher unit tests
- `tests/test_migrator.py` — Migrator unit tests
- `tests/test_cli.py` — CLI unit tests
