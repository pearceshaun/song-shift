from song_shift.models import Track, Playlist, MatchResult


class TestTrack:
    def test_track_creation(self):
        track = Track(
            title="Song",
            artist="Artist",
            album="Album",
            provider_id="123",
            provider="tidal",
            isrc="USRC12345",
            duration_ms=240000,
        )
        assert track.title == "Song"
        assert track.artist == "Artist"
        assert track.album == "Album"
        assert track.provider_id == "123"
        assert track.provider == "tidal"
        assert track.isrc == "USRC12345"
        assert track.duration_ms == 240000

    def test_track_equality(self):
        track1 = Track(
            title="Song",
            artist="Artist",
            album="Album",
            provider_id="123",
            provider="tidal",
        )
        track2 = Track(
            title="Song",
            artist="Artist",
            album="Album",
            provider_id="123",
            provider="tidal",
        )
        assert track1 == track2

    def test_track_display_str(self):
        track = Track(
            title="Bohemian Rhapsody",
            artist="Queen",
            album="A Night at the Opera",
            provider_id="456",
            provider="tidal",
        )
        assert str(track) == "Queen - Bohemian Rhapsody"


class TestPlaylist:
    def test_playlist_creation(self):
        playlist = Playlist(
            id="pl-1",
            name="My Playlist",
            description="A great playlist",
            track_count=10,
            provider="tidal",
        )
        assert playlist.id == "pl-1"
        assert playlist.name == "My Playlist"
        assert playlist.description == "A great playlist"
        assert playlist.track_count == 10
        assert playlist.provider == "tidal"
        assert playlist.tracks == []


class TestMatchResult:
    def test_match_result_creation(self):
        source = Track(
            title="Song",
            artist="Artist",
            album="Album",
            provider_id="1",
            provider="apple_music",
        )
        matched = Track(
            title="Song",
            artist="Artist",
            album="Album",
            provider_id="2",
            provider="tidal",
        )
        result = MatchResult(
            source_track=source,
            matched_track=matched,
            method="isrc",
            confidence=1.0,
        )
        assert result.source_track == source
        assert result.matched_track == matched
        assert result.method == "isrc"
        assert result.confidence == 1.0

    def test_match_result_is_matched(self):
        source = Track(
            title="Song",
            artist="Artist",
            album="Album",
            provider_id="1",
            provider="apple_music",
        )
        matched = Track(
            title="Song",
            artist="Artist",
            album="Album",
            provider_id="2",
            provider="tidal",
        )
        result_matched = MatchResult(
            source_track=source,
            matched_track=matched,
            method="isrc",
            confidence=1.0,
        )
        result_unmatched = MatchResult(
            source_track=source,
            matched_track=None,
            method="none",
            confidence=0.0,
        )
        assert result_matched.is_matched is True
        assert result_unmatched.is_matched is False
