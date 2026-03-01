# Song-Shift Implementation Plan

A CLI application for migrating playlists between music streaming service providers, starting with Apple Music and Tidal.

---

## Table of Contents

1. [Language and Framework Choice](#1-language-and-framework-choice)
2. [Project Structure and Architecture](#2-project-structure-and-architecture)
3. [Apple Music API Integration](#3-apple-music-api-integration)
4. [Tidal API Integration](#4-tidal-api-integration)
5. [Core Data Model](#5-core-data-model)
6. [Song Matching Strategy](#6-song-matching-strategy)
7. [CLI Interface Design](#7-cli-interface-design)
8. [Error Handling and Edge Cases](#8-error-handling-and-edge-cases)
9. [Dependencies](#9-dependencies)
10. [Implementation Phases](#10-implementation-phases)

---

## 1. Language and Framework Choice

**Decision: Python 3.11**

### Rationale

| Criterion | Python | Go | Rust | Node |
|---|---|---|---|---|
| Music API libraries | Excellent (`tidalapi`, `applemusicpy`) | Minimal | None | Moderate |
| CLI frameworks | Excellent (Typer, Click, Rich) | Good (Cobra) | Good (Clap) | Moderate |
| Dev velocity | Highest | Medium | Lowest | Medium |
| Async I/O | Good (`asyncio`, `httpx`) | Excellent | Excellent | Good |
| Extensibility | Excellent (dynamic, plugins easy) | Good | Good | Good |
| Distribution | Good (`pipx`, `uv`) | Best (single binary) | Best (single binary) | Worst |

Python wins decisively on ecosystem. Both the `tidalapi` and `applemusicpy` libraries are mature Python packages. No comparable libraries exist for Go or Rust. The rapid prototyping speed of Python also suits an application that will need to adapt as provider APIs evolve.

### Tooling

- **Package manager**: `uv` for fast dependency resolution and virtual environment management
- **CLI framework**: Typer (built on Click, type-hint driven, auto-generated help, shell completion)
- **Terminal UX**: Rich (progress bars, tables, colored output, spinners)
- **Project metadata**: `pyproject.toml` (PEP 621)
- **Testing**: pytest
- **Linting/Formatting**: ruff

---

## 2. Project Structure and Architecture

### Directory Layout

```
song-shift/
├── pyproject.toml              # Project metadata, dependencies, entry points
├── README.md                   # User-facing documentation
├── PLAN.md                     # This file
├── LICENSE
├── .gitignore
├── .env.example                # Template for required environment variables
│
├── src/
│   └── song_shift/
│       ├── __init__.py         # Package version
│       ├── cli.py              # Typer app, commands, flags
│       ├── config.py           # Configuration loading (env, YAML, CLI args)
│       ├── models.py           # Provider-agnostic data models
│       ├── matcher.py          # Song matching engine (ISRC + fuzzy)
│       ├── transfer.py         # Orchestration: read source -> match -> write dest
│       ├── auth/
│       │   ├── __init__.py
│       │   ├── token_store.py  # Persist/load OAuth tokens to ~/.config/song-shift/
│       │   └── server.py       # Minimal local HTTP server for OAuth callbacks
│       └── providers/
│           ├── __init__.py     # Provider registry and base interface
│           ├── base.py         # Abstract base class for all providers
│           ├── apple_music.py  # Apple Music provider implementation
│           └── tidal.py        # Tidal provider implementation
│
├── tests/
│   ├── conftest.py             # Shared fixtures
│   ├── test_matcher.py         # Matching algorithm tests
│   ├── test_models.py          # Data model tests
│   ├── test_transfer.py        # Transfer orchestration tests
│   ├── test_apple_music.py     # Apple Music provider tests
│   └── test_tidal.py           # Tidal provider tests
│
└── scripts/
    └── apple_music_auth.html   # Minimal HTML page for Apple Music user token acquisition
```

### Provider Abstraction (Plugin Pattern)

The core abstraction is in `src/song_shift/providers/base.py`:

```python
from abc import ABC, abstractmethod
from song_shift.models import Playlist, Track

class MusicProvider(ABC):
    """Abstract base class all providers must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name, e.g. 'Apple Music'."""
        ...

    @property
    @abstractmethod
    def slug(self) -> str:
        """Machine identifier, e.g. 'apple-music'."""
        ...

    @abstractmethod
    async def authenticate(self) -> None:
        """Perform authentication flow. May open browser, prompt user, etc."""
        ...

    @abstractmethod
    async def is_authenticated(self) -> bool:
        """Check if current session is valid."""
        ...

    @abstractmethod
    async def get_playlists(self) -> list[Playlist]:
        """Return all playlists for the authenticated user."""
        ...

    @abstractmethod
    async def get_playlist_tracks(self, playlist_id: str) -> list[Track]:
        """Return all tracks in a given playlist."""
        ...

    @abstractmethod
    async def search_track(self, query: str) -> list[Track]:
        """Search for tracks by text query."""
        ...

    @abstractmethod
    async def lookup_track_by_isrc(self, isrc: str) -> Track | None:
        """Look up a track by its ISRC code. Returns None if not found."""
        ...

    @abstractmethod
    async def create_playlist(self, name: str, description: str = "") -> Playlist:
        """Create a new empty playlist."""
        ...

    @abstractmethod
    async def add_tracks_to_playlist(
        self, playlist_id: str, track_ids: list[str]
    ) -> None:
        """Add tracks (by provider-specific IDs) to an existing playlist."""
        ...
```

### Provider Registry

```python
# src/song_shift/providers/__init__.py

_registry: dict[str, type[MusicProvider]] = {}

def register_provider(cls: type[MusicProvider]) -> type[MusicProvider]:
    """Decorator to register a provider class."""
    instance = cls.__new__(cls)
    _registry[instance.slug] = cls
    return cls

def get_provider(slug: str) -> type[MusicProvider]:
    """Look up a registered provider by slug."""
    if slug not in _registry:
        available = ", ".join(_registry.keys())
        raise ValueError(f"Unknown provider '{slug}'. Available: {available}")
    return _registry[slug]

def list_providers() -> list[str]:
    """Return all registered provider slugs."""
    return list(_registry.keys())
```

Each provider file uses the `@register_provider` decorator at class definition, so importing the providers module automatically registers everything. Adding a new provider requires only creating a new file in `providers/` and decorating the class.

---

## 3. Apple Music API Integration

### Authentication Flow

Apple Music requires two tokens:

1. **Developer Token (JWT)**: Generated server-side, signed with ES256 using a MusicKit private key (.p8 file). Valid for up to 180 days.
   - Required credentials: Team ID (10 chars), Key ID, Private Key (.p8 file)
   - JWT header: `{"alg": "ES256", "kid": "<Key ID>"}`
   - JWT payload: `{"iss": "<Team ID>", "iat": <now>, "exp": <now + up to 180 days>}`
   - Signed using the ES256 algorithm via PyJWT with the `cryptography` backend

2. **Music User Token (MUT)**: Required for accessing/modifying user library data. There is no headless OAuth flow; the token must be obtained through MusicKit JS in a browser.
   - **CLI strategy**: The tool ships a minimal HTML file (`scripts/apple_music_auth.html`) that the `song-shift auth apple-music` command serves via a local HTTP server (localhost:9876). The user opens this page, clicks "Authorize", signs in with their Apple ID, and the resulting Music User Token is captured via a callback and stored in `~/.config/song-shift/apple_music_token.json`.
   - Token expires after approximately 6 months with no refresh mechanism. The tool must detect expiry and prompt re-authentication.

### Key API Endpoints

| Operation | Method | Endpoint | Notes |
|---|---|---|---|
| List user playlists | GET | `/v1/me/library/playlists` | Paginated, alphabetical |
| Get playlist tracks | GET | `/v1/me/library/playlists/{id}/tracks` | Paginated |
| Search catalog | GET | `/v1/catalog/{storefront}/search?term={q}&types=songs` | Text search |
| Lookup by ISRC | GET | `/v1/catalog/{storefront}/songs?filter[isrc]={isrc}` | Up to 25 ISRCs at once |
| Create playlist | POST | `/v1/me/library/playlists` | Body: `LibraryPlaylistCreationRequest` |
| Add tracks to playlist | POST | `/v1/me/library/playlists/{id}/tracks` | Body: array of `{id, type}` objects |

### Required Headers

```
Authorization: Bearer <developer_token>
Music-User-Token: <music_user_token>
Content-Type: application/json; charset=utf-8
```

### Pagination

Library endpoints return paginated results. The response includes a `next` URL in the `meta` object when more results exist. The default page size is 25; the maximum is 100 (via `?limit=100`). The implementation must follow `next` links until exhausted.

### Rate Limits

Approximately 20 requests per second. The API returns HTTP 429 with `RATE_LIMIT_EXCEEDED` when exceeded. Catalog endpoints benefit from server-side caching; library endpoints do not.

---

## 4. Tidal API Integration

### Authentication Flow

Tidal uses OAuth2. The `tidalapi` library handles the flow natively.

**Two approaches available:**

1. **OAuth Simple (recommended for CLI)**: `session.login_oauth_simple()` prints a URL to the console. The user visits it in their browser, logs in, and links their account. The method blocks until auth completes.

2. **OAuth Advanced**: `session.login_oauth()` returns a `LinkLogin` object with `user_code` and `verification_uri`, plus a `Future` that polls until complete. Useful for displaying the code in a styled way via Rich.

**Session persistence**: `tidalapi` supports saving and loading sessions. The tool stores session data (access token, refresh token, expiry) in `~/.config/song-shift/tidal_session.json`. On subsequent runs, load the session and let `tidalapi` handle token refresh automatically.

### Key Operations via tidalapi

| Operation | Method | Notes |
|---|---|---|
| Authenticate | `session.login_oauth_simple()` | Prints URL, blocks until complete |
| Load saved session | `session.load_oauth_session(...)` | Restores prior auth |
| List playlists | `session.user.playlists()` | Returns user's playlists |
| Get playlist tracks | `playlist.tracks()` | Returns list of Track objects |
| Search tracks | `session.search(query, models=[tidalapi.Track])` | Text search |
| Lookup by ISRC | `session.get_tracks_by_isrc(isrc)` | Direct ISRC lookup |
| Create playlist | `session.user.create_playlist(name, description)` | Returns new playlist |
| Add tracks | `playlist.add([track_id1, ...])` | Add by Tidal track IDs |
| Track ISRC | `track.isrc` | ISRC attribute on Track objects |

### Implementation Notes

- `tidalapi` is synchronous. Wrap calls in `asyncio.to_thread()` to avoid blocking the async event loop.
- The library handles pagination internally for most methods.
- Track objects include `name`, `artist.name`, `album.name`, `isrc`, `duration`, `id`.

---

## 5. Core Data Model

Defined in `src/song_shift/models.py` using Python dataclasses:

```python
from dataclasses import dataclass, field
from enum import Enum


class ProviderSlug(str, Enum):
    APPLE_MUSIC = "apple-music"
    TIDAL = "tidal"


@dataclass(frozen=True)
class Track:
    """Provider-agnostic representation of a single track."""
    title: str
    artist: str
    album: str
    isrc: str | None = None
    duration_seconds: int | None = None
    provider_id: str | None = None
    provider: ProviderSlug | None = None


@dataclass
class Playlist:
    """Provider-agnostic representation of a playlist."""
    name: str
    description: str = ""
    tracks: list[Track] = field(default_factory=list)
    provider_id: str | None = None
    provider: ProviderSlug | None = None
    track_count: int = 0


class MatchQuality(str, Enum):
    """How well a track matched across providers."""
    EXACT_ISRC = "exact_isrc"
    HIGH_CONFIDENCE = "high_confidence"
    LOW_CONFIDENCE = "low_confidence"
    NOT_FOUND = "not_found"


@dataclass
class MatchResult:
    """Result of attempting to match a source track in the destination."""
    source_track: Track
    matched_track: Track | None = None
    quality: MatchQuality = MatchQuality.NOT_FOUND
    score: float = 0.0


@dataclass
class TransferReport:
    """Summary of a playlist transfer operation."""
    source_playlist: Playlist
    destination_playlist: Playlist | None
    matches: list[MatchResult] = field(default_factory=list)

    @property
    def matched_count(self) -> int:
        return sum(1 for m in self.matches if m.quality != MatchQuality.NOT_FOUND)

    @property
    def not_found_count(self) -> int:
        return sum(1 for m in self.matches if m.quality == MatchQuality.NOT_FOUND)

    @property
    def exact_count(self) -> int:
        return sum(1 for m in self.matches if m.quality == MatchQuality.EXACT_ISRC)
```

### Design Decisions

- **`frozen=True` on Track**: Tracks are value objects. Immutability prevents accidental mutation during matching.
- **`isrc` is optional**: Not all providers expose ISRC for every track, and library tracks in Apple Music may not include it without an additional catalog lookup.
- **`provider_id` preserved**: Needed when writing back to a destination provider (e.g., adding tracks to a Tidal playlist requires Tidal track IDs).
- **`MatchResult` captures quality**: The user can review low-confidence matches before committing the transfer.

---

## 6. Song Matching Strategy

Song matching is the most critical and error-prone part of cross-provider playlist migration. The strategy uses a tiered approach.

### Tier 1: ISRC Exact Match (Fastest, Most Accurate)

ISRC (International Standard Recording Code) is a 12-character globally unique identifier for a sound recording. Both Apple Music and Tidal expose ISRCs and support ISRC-based lookup.

```
Source track has ISRC "USAT21600001"
  -> Query destination: lookup_track_by_isrc("USAT21600001")
  -> If exactly one result: EXACT_ISRC match (score: 1.0)
  -> If multiple results: pick the one with closest album name match
  -> If zero results: fall through to Tier 2
```

**Batching**: Apple Music supports up to 25 ISRCs per request. Batch ISRC lookups to minimize API calls.

**Caveat**: The same ISRC can map to multiple catalog entries (album version vs. single, different regional releases). When multiple matches are returned, prefer the one whose album name most closely matches the source.

### Tier 2: Text Search with Fuzzy Matching

When ISRC is unavailable or returns no results:

```
Query: "{track title} {artist name}"
  -> Search destination catalog
  -> Score each result using weighted fuzzy matching:
       - Title similarity:  40% weight
       - Artist similarity: 40% weight
       - Album similarity:  15% weight
       - Duration delta:     5% weight (penalize >5s difference)
  -> If best score >= 0.85: HIGH_CONFIDENCE match
  -> If best score >= 0.60: LOW_CONFIDENCE match (flag for review)
  -> If best score < 0.60:  NOT_FOUND
```

### Fuzzy Matching Implementation

Use `thefuzz` (formerly `fuzzywuzzy`) with `python-Levenshtein` for fast string similarity:

```python
from thefuzz import fuzz

def compute_match_score(source: Track, candidate: Track) -> float:
    title_score = fuzz.token_sort_ratio(
        normalize(source.title), normalize(candidate.title)
    ) / 100.0
    artist_score = fuzz.token_sort_ratio(
        normalize(source.artist), normalize(candidate.artist)
    ) / 100.0
    album_score = fuzz.token_sort_ratio(
        normalize(source.album), normalize(candidate.album)
    ) / 100.0

    duration_score = 1.0
    if source.duration_seconds and candidate.duration_seconds:
        delta = abs(source.duration_seconds - candidate.duration_seconds)
        duration_score = max(0.0, 1.0 - (delta / 30.0))

    return (
        0.40 * title_score
        + 0.40 * artist_score
        + 0.15 * album_score
        + 0.05 * duration_score
    )
```

### Normalization

Before comparing strings, normalize them:
- Lowercase
- Remove parenthetical suffixes like "(Remastered)", "(Deluxe)", "(feat. X)"
- Remove common noise words: "the", "&" vs "and"
- Strip accents/diacritics using `unicodedata.normalize("NFKD", ...)`
- Collapse multiple spaces

---

## 7. CLI Interface Design

Built with Typer and Rich. Entry point: `song-shift`.

### Commands

```
song-shift auth <provider>          # Authenticate with a provider
song-shift list <provider>          # List playlists from a provider
song-shift transfer <src> <dst>     # Transfer playlists from source to destination
song-shift providers                # List available providers
```

### Detailed Command Signatures

```
song-shift auth apple-music
    Launches local web server, opens browser for Apple Music authorization.
    Stores token in ~/.config/song-shift/

song-shift auth tidal
    Initiates Tidal OAuth flow, prints link + code.
    Stores session in ~/.config/song-shift/

song-shift list <provider>
    --format [table|json]           # Output format (default: table)
    Lists all playlists with name, track count, and ID.

song-shift transfer <source> <destination>
    --playlist <name-or-id>         # Transfer a specific playlist (repeatable)
    --all                           # Transfer all playlists
    --dry-run                       # Show what would happen without writing
    --skip-low-confidence           # Only transfer exact + high confidence matches
    --include-low-confidence        # Include low confidence matches (default: prompt)
    --output-report <path>          # Save transfer report as JSON
    --yes                           # Skip confirmation prompts

song-shift providers
    Lists all registered providers and their auth status.
```

### Example Usage

```bash
# First-time setup
song-shift auth tidal
song-shift auth apple-music

# See what's available
song-shift list apple-music

# Transfer a specific playlist
song-shift transfer apple-music tidal --playlist "Road Trip Mix"

# Transfer everything, non-interactive
song-shift transfer apple-music tidal --all --skip-low-confidence --yes

# Dry run to preview
song-shift transfer tidal apple-music --playlist "Favorites" --dry-run
```

### UX Design

**Progress display** (Rich):
```
Transferring "Road Trip Mix" (147 tracks)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 147/147

Match Results:
┌─────────┬───────┬────────────┐
│ Quality │ Count │ Percentage │
├─────────┼───────┼────────────┤
│ Exact   │   132 │ 90%        │
│ High    │     9 │ 6%         │
│ Low     │     3 │ 2%         │
│ Missing │     3 │ 2%         │
└─────────┴───────┴────────────┘

Missing tracks:
  1. "Obscure B-Side" by Indie Band
  2. "Regional Release" by Local Artist
  3. "Removed Track" by Former Artist

Low confidence matches (review):
  1. "Live Version" by Band -> "Studio Version" by Band (score: 0.72)

Proceed with transfer? [Y/n]
```

### Configuration File

`~/.config/song-shift/config.yaml` (optional, overrides defaults):

```yaml
default_source: apple-music
default_destination: tidal
storefront: us
match_threshold_high: 0.85
match_threshold_low: 0.60
skip_low_confidence: false
```

---

## 8. Error Handling and Edge Cases

### Rate Limiting

Apply rate-limit-aware throttling globally using a retry decorator with exponential backoff. Maintain a semaphore or token bucket to keep requests below ~15/s for Apple Music (leaving headroom below the 20/s limit). Tidal rate limits are undocumented; the `tidalapi` library raises `TooManyRequests` which should be caught and retried.

### Pagination

Both APIs return paginated results. Implement a generic async pagination helper that follows `next` links or increments offsets until all results are collected.

### Missing Songs

Tracks that cannot be matched are collected in the `TransferReport` with `quality=NOT_FOUND`. The CLI displays these clearly after the transfer and optionally writes them to a JSON report. Users can manually resolve these later.

### Duplicate Playlists

Before creating a playlist in the destination, check if one with the same name already exists. Offer options:
- `--overwrite`: Clear existing playlist and re-populate
- `--append`: Add only tracks not already in the destination playlist
- Default: Create with a " (2)" suffix or prompt the user

### Authentication Expiry

- **Apple Music**: MUT expires after ~6 months with no refresh. Detect 401 responses and guide the user to re-authenticate.
- **Tidal**: `tidalapi` handles refresh tokens automatically. If the refresh token is also expired, prompt re-auth.

### Network Errors

Wrap all HTTP calls in try/except for connection errors, timeouts, and unexpected status codes. Display user-friendly messages.

### Large Playlists

For playlists with hundreds or thousands of tracks:
- Fetch tracks in paginated batches
- Match tracks concurrently (bounded concurrency with `asyncio.Semaphore`, limit ~5 concurrent matches to respect rate limits)
- Add tracks to destination playlist in batches

### Edge Cases

- **Empty playlists**: Skip with a warning rather than creating empty playlists in the destination
- **Character encoding**: Both APIs use UTF-8. Normalize unicode (NFC form) before comparison
- **Catalog differences**: Some tracks exist on one service but not the other due to licensing. Communicate this clearly as expected behavior, not an error

---

## 9. Dependencies

### Runtime Dependencies

```toml
[project]
dependencies = [
    "typer>=0.15.0",           # CLI framework
    "rich>=14.0.0",            # Terminal formatting, progress bars, tables
    "httpx>=0.28.0",           # Async HTTP client for Apple Music API
    "tidalapi>=0.8.11",        # Tidal API wrapper
    "PyJWT[crypto]>=2.7.0",    # JWT generation for Apple Music developer tokens
    "thefuzz[speedup]>=0.22",  # Fuzzy string matching (includes python-Levenshtein)
    "pyyaml>=6.0",             # Configuration file parsing
    "platformdirs>=4.0",       # Cross-platform config directory resolution
]
```

### Development Dependencies

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "ruff>=0.9.0",
    "respx>=0.22",             # Mock httpx requests in tests
    "mypy>=1.14",
]
```

### Entry Point

```toml
[project.scripts]
song-shift = "song_shift.cli:app"
```

---

## 10. Implementation Phases

### Phase 1: Foundation

**Goal**: Skeleton project with models, provider interface, and CLI scaffold.

1. Initialize project with `uv init`; set up `pyproject.toml` with all metadata and dependencies
2. Create directory structure (`src/song_shift/`, `tests/`, `scripts/`)
3. Implement `models.py` -- all dataclasses (`Track`, `Playlist`, `MatchResult`, `MatchQuality`, `TransferReport`)
4. Implement `providers/base.py` -- `MusicProvider` ABC
5. Implement `providers/__init__.py` -- provider registry with `@register_provider` decorator
6. Scaffold `cli.py` with Typer -- define command stubs for `auth`, `list`, `transfer`, `providers`
7. Implement `config.py` -- load config from `~/.config/song-shift/config.yaml`, merge with env vars and CLI flags
8. Implement `auth/token_store.py` -- save/load JSON credential files
9. Write unit tests for models and config loading
10. Set up ruff for linting and formatting; configure in `pyproject.toml`

**Deliverable**: `song-shift providers` works and returns an empty list. All models and interfaces compile and pass type checks.

### Phase 2: Tidal Provider

**Goal**: Full Tidal integration -- auth, read playlists, search, create playlists.

1. Implement `providers/tidal.py` with all `MusicProvider` methods
2. Implement session persistence (save/load from token store)
3. Wire `song-shift auth tidal` and `song-shift list tidal` commands
4. Write integration tests (with mocked tidalapi Session)

**Deliverable**: `song-shift auth tidal` authenticates. `song-shift list tidal` shows real playlists.

### Phase 3: Apple Music Provider

**Goal**: Full Apple Music integration -- auth, read playlists, search, ISRC lookup, create playlists.

1. Implement developer token generation (ES256 JWT via PyJWT)
2. Create `scripts/apple_music_auth.html` for MusicKit JS auth flow
3. Implement `auth/server.py` -- local HTTP server for OAuth callback
4. Implement all `MusicProvider` methods using httpx against the Apple Music REST API
5. Wire `song-shift auth apple-music` and `song-shift list apple-music` commands
6. Write tests with mocked httpx responses (using `respx`)

**Deliverable**: `song-shift auth apple-music` opens browser and captures token. `song-shift list apple-music` shows real playlists.

### Phase 4: Matching Engine

**Goal**: Robust song matching with ISRC primary and fuzzy fallback.

1. Implement `matcher.py` -- `normalize()`, `compute_match_score()`, `match_track()`, `match_playlist()`
2. Write comprehensive unit tests for matching edge cases (feat. variations, remastered editions, unicode, duration disambiguation)

**Deliverable**: `match_playlist()` correctly matches a test set of tracks with >90% accuracy.

### Phase 5: Transfer Orchestration

**Goal**: End-to-end playlist transfer with progress display and reporting.

1. Implement `transfer.py` -- `transfer_playlist()`, `transfer_all_playlists()`, `TransferReport` generation
2. Wire `song-shift transfer` command with all flags (`--playlist`, `--all`, `--dry-run`, `--skip-low-confidence`, `--output-report`, `--yes`)
3. Rich progress bar, match results table, missing tracks display, interactive low-confidence review
4. Handle duplicate playlist names
5. Write end-to-end tests (fully mocked providers)

**Deliverable**: `song-shift transfer apple-music tidal --playlist "My Playlist"` works end-to-end.

### Phase 6: Polish and Release

**Goal**: Production-ready CLI with documentation and packaging.

1. Add `--verbose` / `--quiet` flags for log level control
2. Improve error messages for all failure modes
3. Write README.md with installation, prerequisites, quick start, and command reference
4. Add `.env.example` and `.gitignore`
5. Final test pass
6. Tag v0.1.0

**Deliverable**: Installable, documented, tested v0.1.0 release.

### Future Phases (Post v0.1.0)

- **Spotify provider**: OAuth2 with PKCE, `spotipy` library
- **YouTube Music provider**: `ytmusicapi` library
- **Deezer provider**: Simple OAuth, good ISRC support
- **Bidirectional sync**: Detect changes on both sides and reconcile
- **Interactive match resolution**: TUI (Textual) for reviewing low-confidence matches
- **Batch ISRC cache**: SQLite cache of ISRC-to-provider-ID mappings
- **Web UI**: FastAPI backend + React frontend, reusing the same provider/matcher core
