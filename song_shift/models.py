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


@dataclass
class Playlist:
    id: str
    name: str
    description: str = ""
    track_count: int = 0
    provider: str = ""
    tracks: list[Track] = field(default_factory=list)


@dataclass
class MatchResult:
    source_track: Track
    matched_track: Track | None
    method: str  # "isrc", "fuzzy", or "none"
    confidence: float

    @property
    def is_matched(self) -> bool:
        return self.matched_track is not None
