# YouTube Import Research

## Overview

This document explores adding a YouTube provider to song-shift that can extract
individual songs from YouTube videos containing multiple tracks (e.g. DJ mixes,
compilation videos, "best of" collections).

## The Problem

YouTube music videos often contain multiple songs in a single video. Users want
to import these track lists into song-shift so they can migrate the songs to
streaming services like Apple Music or Tidal.

## Approaches to Extract Song Lists

### Approach 1: YouTube Chapters (Description Timestamps)

Many YouTube uploaders include timestamped track lists in the video description
or as YouTube chapters. This is the simplest and most reliable method.

**How it works:**
1. Fetch video metadata (title, description, chapters) via API
2. Parse timestamps and track names from description or chapter data
3. Convert to `Track` objects for matching on target services

**Tools:**
- **yt-dlp** (Python library, no API key needed): Can extract full video
  metadata including chapters via `extract_info(url, download=False)`. Chapters
  come as `[{"start_time": 0, "end_time": 180, "title": "Artist - Song"}, ...]`
- **YouTube Data API v3** (requires API key, 10k quota/day): Fetch
  `snippet.description` and parse timestamps with regex like
  `r'(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+')`
- **python-youtube** (PyPI wrapper): Simpler Python wrapper around the
  YouTube Data API

**Pros:**
- Fast, no audio processing needed
- Free (yt-dlp) or cheap (YouTube API)
- Accurate when chapters/timestamps exist

**Cons:**
- Not all videos have timestamps or chapters
- Track title format varies wildly ("Artist - Title", "Title by Artist",
  "Title (Artist)", just "Title", etc.)
- Requires parsing heuristics to split artist/title

**Recommendation: This should be the primary approach.** yt-dlp is the best
tool here -- it's free, requires no API key, and its `chapters` field handles
the common case cleanly. Fall back to description regex parsing when chapters
aren't available.

### Approach 2: Audio Fingerprinting (Shazam/ACRCloud)

For videos without timestamps, we can download the audio and identify songs
via audio fingerprinting.

**How it works:**
1. Download audio from YouTube video (yt-dlp)
2. Split audio into segments (e.g., 30-second chunks with overlap)
3. Run each segment through a recognition service
4. Deduplicate and order results

**Tools:**
- **shazamio** (already a dependency!): Free, async, reverse-engineered
  Shazam API. Can recognize songs from audio files
- **ACRCloud**: Commercial audio fingerprinting API. More reliable but
  requires API credentials and has usage costs
- **AudD API**: Commercial music recognition API. Can accept YouTube URLs
  directly
- **pydub / ffmpeg**: For splitting audio into segments

**Existing project:** [Shazam-Tool](https://github.com/in0vik/Shazam-Tool)
combines yt-dlp + pydub + shazamio to identify songs in YouTube mixes.

**Pros:**
- Works even without timestamps/chapters
- Can identify songs the uploader didn't list

**Cons:**
- Slow (must download audio, process segments)
- Less accurate with transitions, mashups, or remixes
- shazamio is reverse-engineered and could break
- Audio quality after YouTube compression may reduce accuracy
- Requires ffmpeg as a system dependency

**Recommendation: This should be a secondary/optional approach.** Since
shazamio is already a dependency, the incremental cost is low. But it should
only be used as a fallback when chapter/timestamp extraction fails.

### Approach 3: YouTube Transcript / Captions

Some music videos have auto-generated or manual captions that mention song
titles. This is generally unreliable for music content.

**Not recommended** -- captions rarely contain useful track metadata for
music compilation videos.

## Recommended Architecture

### New Provider: `YouTubeProvider`

Following the existing provider pattern (similar to `ShazamProvider`), create a
read-only provider:

```python
@register_provider
class YouTubeProvider(MusicProvider):
    name = "youtube"
```

### Authentication

- **yt-dlp approach (recommended):** No authentication needed for public
  videos. For private/unlisted videos, yt-dlp supports cookies or OAuth
- **YouTube API approach:** Requires a Google API key stored in credentials

### Track Extraction Pipeline

```
YouTube URL
    |
    v
[yt-dlp extract_info] --> video metadata (title, description, chapters)
    |
    +--> Has chapters? --> Parse chapter titles into Track objects
    |
    +--> No chapters? --> Parse description for timestamps
    |
    +--> No timestamps? --> (Optional) Audio fingerprinting fallback
                            Download audio -> split -> shazamio recognize
```

### Parsing Chapter/Timestamp Titles into Tracks

The hardest part is parsing free-text chapter titles into artist + title. Common
formats:

| Format                  | Example                        |
|------------------------|--------------------------------|
| `Artist - Title`       | `Daft Punk - Around the World` |
| `Title - Artist`       | `Around the World - Daft Punk` |
| `Artist: Title`        | `Daft Punk: Around the World`  |
| `Title (Artist)`       | `Around the World (Daft Punk)` |
| `Title by Artist`      | `Around the World by Daft Punk`|
| `N. Artist - Title`    | `1. Daft Punk - Around the World` |
| Just `Title`           | `Around the World`             |

**Strategy:**
1. Try splitting on common delimiters (` - `, `: `, ` by `)
2. Strip track numbers (`^\d+[\.\)\s]+`)
3. Use the raw chapter title as a search query on the target service
4. The existing fuzzy matcher will handle minor mismatches

Since song-shift already uses `search_track(query)` with fuzzy matching on
the target service, we don't necessarily need perfect artist/title splitting.
We can pass the full chapter title as the search query and let the target
service + matcher do the work.

### CLI Integration

```bash
# Import from a YouTube video with chapters
song-shift migrate youtube tidal --playlist-id "https://youtu.be/aaKrmYwaOkk"

# Or a dedicated import command
song-shift import youtube "https://youtu.be/aaKrmYwaOkk" --to tidal
```

### Data Flow

```
YouTubeProvider.get_playlist_tracks("https://youtu.be/aaKrmYwaOkk")
  --> yt-dlp.extract_info(url)
  --> parse chapters/description
  --> [Track(title="Song Name", artist="Artist", provider="youtube", ...)]
  --> TrackMatcher matches against target service
  --> PlaylistMigrator creates playlist on target
```

## New Dependency

| Package | Purpose | License | Size |
|---------|---------|---------|------|
| `yt-dlp` | YouTube metadata extraction | Unlicense | ~20MB installed |

yt-dlp is the only new required dependency. shazamio (already installed) covers
the optional audio fingerprinting fallback. ffmpeg would be needed as a system
dependency only for the audio fingerprinting path.

## Implementation Plan

### Phase 1: Core YouTube Provider (MVP)
1. Add `yt-dlp` to `pyproject.toml`
2. Create `song_shift/providers/youtube.py` with `YouTubeProvider`
3. Implement `extract_info` -> chapter parsing -> Track objects
4. Implement description timestamp regex fallback
5. Wire into CLI (use URL as playlist_id)
6. Add tests

### Phase 2: Enhanced Parsing
1. Improve artist/title splitting heuristics
2. Handle edge cases (numbered tracks, parenthetical artists, etc.)
3. Support YouTube playlists (multiple videos)
4. Add `--youtube-api-key` option for users who prefer the official API

### Phase 3: Audio Fingerprinting Fallback (Optional)
1. Add `--recognize` flag to trigger audio fingerprinting
2. Download audio via yt-dlp
3. Split into segments with pydub/ffmpeg
4. Recognize via shazamio
5. Deduplicate and merge with chapter-based results

## Open Questions

1. **Should YouTube be source-only (like Shazam) or also a target?** -- Source-only
   seems appropriate since creating YouTube videos programmatically is a very
   different domain.

2. **How to handle YouTube playlists vs single videos?** -- A YouTube playlist
   could map to a song-shift playlist, while a single multi-track video is more
   like the Shazam CSV import pattern.

3. **Should yt-dlp be an optional dependency?** -- Could make it optional and
   fall back to the YouTube Data API, but yt-dlp is significantly easier to
   use and doesn't require API keys.

4. **Rate limiting / caching:** -- yt-dlp makes HTTP requests to YouTube.
   Should we cache video metadata to avoid repeated fetches during development
   or retries?
