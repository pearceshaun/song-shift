# Playlist Migration — Project Guide

> Operational reference for this loop. Claude reads this each iteration to absorb
> project-specific patterns, commands, and conventions.
> **Behavioral instructions belong in `prompt.md`, not here.**

## Build & Test Commands

```bash
# Primary test command — run after every change (backpressure)
uv run pytest -x -q

# Run tests for a specific file
uv run pytest tests/test_models.py -x -q

# Full test suite with coverage
uv run pytest --tb=short

# Install/sync dependencies
uv sync

# Verify CLI works
uv run python -m song_shift --help
```

## Key Architectural Decisions (already made)

1. **Python with uv** — Use `uv` as package manager. `pyproject.toml` for project metadata. No setup.py, no requirements.txt.
2. **Click for CLI** — Use Click (not Typer, not argparse). CLI group at `song_shift.cli:cli`. Entry point defined in pyproject.toml `[project.scripts]`.
3. **Provider pattern** — Abstract base class `MusicProvider` in `song_shift/providers/base.py`. Each provider is a subclass. Providers register themselves via a module-level registry dict.
4. **httpx for HTTP** — Use `httpx` (not requests) for all HTTP calls. Synchronous client only (no async).
5. **tidalapi for Tidal** — Use the `tidalapi` package for Tidal API access. Do NOT use raw HTTP for Tidal.
6. **PyJWT for Apple Music** — Use `PyJWT` with `cryptography` backend for ES256 JWT signing of Apple Music developer tokens.
7. **rapidfuzz for matching** — Use `rapidfuzz.fuzz.token_sort_ratio` for fuzzy string matching. Threshold: 80.
8. **Credential storage** — JSON file at `~/.config/song-shift/credentials.json`. Use `CredentialStore` class from `song_shift/config.py`. File permissions: 0o600.
9. **dataclasses for models** — Use stdlib `@dataclass` (not Pydantic, not attrs). Keep models in `song_shift/models.py`.
10. **Test isolation** — Use pytest `tmp_path` fixture for any tests that touch the filesystem. Mock all external API calls. Never make real network requests in tests.
11. **ISRC-first matching** — Track matching tries ISRC exact match first, then falls back to fuzzy. This is the only matching strategy — do not add other strategies.
12. **No async** — All code is synchronous. Do not use async/await anywhere.

## Codebase Patterns to Follow

### Project Structure
```
song-shift/
├── pyproject.toml
├── .gitignore
├── .env.example
├── song_shift/
│   ├── __init__.py          # Version: __version__ = "0.1.0"
│   ├── __main__.py          # from song_shift.cli import cli; cli()
│   ├── models.py            # Track, Playlist, MatchResult dataclasses
│   ├── config.py            # CredentialStore
│   ├── matcher.py           # TrackMatcher
│   ├── migrator.py          # PlaylistMigrator, MigrationReport
│   ├── cli.py               # Click CLI group
│   └── providers/
│       ├── __init__.py      # Imports + registers all providers
│       ├── base.py          # MusicProvider ABC + registry
│       ├── tidal.py         # TidalProvider
│       └── apple_music.py   # AppleMusicProvider
└── tests/
    ├── __init__.py
    ├── conftest.py           # Shared fixtures
    ├── test_models.py
    ├── test_config.py
    ├── test_provider_base.py
    ├── test_matcher.py
    ├── test_migrator.py
    ├── test_cli.py
    └── providers/
        ├── __init__.py
        ├── test_tidal.py
        └── test_apple_music.py
```

### Model Pattern
```python
# song_shift/models.py
from dataclasses import dataclass, field

@dataclass
class Track:
    title: str
    artist: str
    album: str
    provider_id: str
    provider: str
    isrc: str | None = None
    duration_ms: int | None = None

    def __str__(self) -> str:
        return f"{self.artist} - {self.title}"
```

### Provider Pattern
```python
# song_shift/providers/base.py
from abc import ABC, abstractmethod

_registry: dict[str, type["MusicProvider"]] = {}

def register_provider(cls: type["MusicProvider"]) -> type["MusicProvider"]:
    _registry[cls.name] = cls
    return cls

def get_provider(name: str) -> type["MusicProvider"] | None:
    return _registry.get(name)

def list_providers() -> list[str]:
    return list(_registry.keys())

class MusicProvider(ABC):
    name: str  # Class variable, set by each subclass

    @abstractmethod
    def authenticate(self) -> None: ...

    @abstractmethod
    def is_authenticated(self) -> bool: ...
    # ... etc
```

```python
# song_shift/providers/tidal.py
from song_shift.providers.base import MusicProvider, register_provider

@register_provider
class TidalProvider(MusicProvider):
    name = "tidal"
    # ...
```

### Test Pattern
```python
# tests/test_models.py
import pytest
from song_shift.models import Track, Playlist, MatchResult

class TestTrack:
    def test_track_creation(self):
        track = Track(
            title="Song", artist="Artist", album="Album",
            provider_id="123", provider="tidal", isrc="USRC12345"
        )
        assert track.title == "Song"
        assert track.isrc == "USRC12345"
```

### CLI Pattern
```python
# song_shift/cli.py
import click

@click.group()
def cli():
    """Song Shift — migrate playlists between music services."""
    pass

@cli.command()
@click.argument("provider_name")
def auth(provider_name: str):
    """Authenticate with a music service."""
    # ...
```

### Testing
- **Framework:** pytest (no unittest classes needed, but grouping with classes is fine)
- **Fixtures:** Use pytest `tmp_path` for filesystem tests, `monkeypatch` for env vars
- **Mocking:** Use `unittest.mock.patch`, `MagicMock`, `Mock` from stdlib
- **HTTP mocking:** For Apple Music tests, use `unittest.mock.patch("httpx.Client")` or mock at the provider method level
- **Tidal mocking:** Mock `tidalapi.Session` and its methods
- **CLI testing:** Use `click.testing.CliRunner` with `runner.invoke(cli, ["auth", "tidal"])`
- **Test file naming:** `test_{module}.py` in `tests/` mirroring source structure
- **Test function naming:** `test_{behaviour_description}` using snake_case
- **No network calls:** Every test must work offline. All external calls must be mocked.

## Branch Info

- Working branch: `claude/playlist-migration-plan-SfdvN`
- Base branch: `claude/playlist-migration-plan-SfdvN`
- Push command: `git push -u origin claude/playlist-migration-plan-SfdvN`
- **NEVER push to any other branch**
