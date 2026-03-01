from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from song_shift.cli import cli
from song_shift.models import MatchResult, Playlist, Track


def _make_track(title="Song", artist="Artist", album="Album", provider="tidal",
                provider_id="t1", isrc="USRC12345"):
    return Track(
        title=title, artist=artist, album=album,
        provider_id=provider_id, provider=provider, isrc=isrc,
    )


def _make_playlist(id="pl1", name="My Playlist", track_count=3, provider="tidal"):
    return Playlist(id=id, name=name, track_count=track_count, provider=provider)


class TestAuthCommand:
    def test_auth_command_runs_provider_auth(self):
        mock_provider = MagicMock()
        mock_provider_cls = MagicMock(return_value=mock_provider)

        with patch("song_shift.cli.get_provider", return_value=mock_provider_cls):
            runner = CliRunner()
            result = runner.invoke(cli, ["auth", "tidal"])

        assert result.exit_code == 0
        mock_provider.authenticate.assert_called_once()
        assert "Authenticated" in result.output

    def test_auth_unknown_provider(self):
        with patch("song_shift.cli.get_provider", return_value=None), \
             patch("song_shift.cli.list_providers", return_value=["tidal", "apple_music"]):
            runner = CliRunner()
            result = runner.invoke(cli, ["auth", "spotify"])

        assert result.exit_code != 0
        assert "Unknown provider" in result.output


class TestListCommand:
    def test_list_command_shows_playlists(self):
        mock_provider = MagicMock()
        mock_provider.is_authenticated.return_value = True
        mock_provider.list_playlists.return_value = [
            _make_playlist(name="Rock Hits", track_count=25),
            _make_playlist(id="pl2", name="Chill Vibes", track_count=10),
        ]
        mock_provider_cls = MagicMock(return_value=mock_provider)

        with patch("song_shift.cli.get_provider", return_value=mock_provider_cls):
            runner = CliRunner()
            result = runner.invoke(cli, ["list", "tidal"])

        assert result.exit_code == 0
        assert "Rock Hits" in result.output
        assert "25 tracks" in result.output
        assert "Chill Vibes" in result.output

    def test_list_unauthenticated_provider(self):
        mock_provider = MagicMock()
        mock_provider.is_authenticated.return_value = False
        mock_provider_cls = MagicMock(return_value=mock_provider)

        with patch("song_shift.cli.get_provider", return_value=mock_provider_cls):
            runner = CliRunner()
            result = runner.invoke(cli, ["list", "tidal"])

        assert result.exit_code != 0
        assert "Not authenticated" in result.output


class TestMigrateCommand:
    def test_migrate_command_runs_migration(self):
        source_track = _make_track(provider="apple_music", provider_id="a1")
        target_track = _make_track(provider="tidal", provider_id="t1")

        source_provider = MagicMock()
        source_provider.is_authenticated.return_value = True
        source_provider.get_playlist_tracks.return_value = [source_track]
        source_provider.list_playlists.return_value = [
            _make_playlist(id="pl1", name="Source Playlist", provider="apple_music"),
        ]

        target_provider = MagicMock()
        target_provider.is_authenticated.return_value = True
        target_provider.create_playlist.return_value = _make_playlist(
            id="new_pl", name="Source Playlist", provider="tidal",
        )

        match_result = MatchResult(
            source_track=source_track, matched_track=target_track,
            method="isrc", confidence=1.0,
        )

        def _get_provider(name):
            if name == "apple_music":
                return MagicMock(return_value=source_provider)
            if name == "tidal":
                return MagicMock(return_value=target_provider)
            return None

        with patch("song_shift.cli.get_provider", side_effect=_get_provider), \
             patch("song_shift.cli.PlaylistMigrator") as mock_migrator_cls:
            mock_migrator = MagicMock()
            mock_migrator.matcher.match_tracks.return_value = [match_result]
            mock_migrator_cls.return_value = mock_migrator

            runner = CliRunner()
            result = runner.invoke(cli, [
                "migrate", "apple_music", "tidal", "--playlist-id", "pl1",
            ])

        assert result.exit_code == 0
        target_provider.create_playlist.assert_called_once()
        target_provider.add_tracks_to_playlist.assert_called_once()
        assert "1/1 tracks matched" in result.output

    def test_migrate_dry_run(self):
        source_track = _make_track(provider="apple_music", provider_id="a1")
        target_track = _make_track(provider="tidal", provider_id="t1")

        source_provider = MagicMock()
        source_provider.is_authenticated.return_value = True
        source_provider.get_playlist_tracks.return_value = [source_track]
        source_provider.list_playlists.return_value = [
            _make_playlist(id="pl1", name="Source Playlist", provider="apple_music"),
        ]

        target_provider = MagicMock()
        target_provider.is_authenticated.return_value = True

        match_result = MatchResult(
            source_track=source_track, matched_track=target_track,
            method="isrc", confidence=1.0,
        )

        def _get_provider(name):
            if name == "apple_music":
                return MagicMock(return_value=source_provider)
            if name == "tidal":
                return MagicMock(return_value=target_provider)
            return None

        with patch("song_shift.cli.get_provider", side_effect=_get_provider), \
             patch("song_shift.cli.PlaylistMigrator") as mock_migrator_cls:
            mock_migrator = MagicMock()
            mock_migrator.matcher.match_tracks.return_value = [match_result]
            mock_migrator_cls.return_value = mock_migrator

            runner = CliRunner()
            result = runner.invoke(cli, [
                "migrate", "apple_music", "tidal",
                "--playlist-id", "pl1", "--dry-run",
            ])

        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        target_provider.create_playlist.assert_not_called()
        target_provider.add_tracks_to_playlist.assert_not_called()

    def test_migrate_shows_summary(self):
        source_tracks = [
            _make_track(title="Song A", provider_id="a1", provider="apple_music"),
            _make_track(title="Song B", provider_id="a2", provider="apple_music", isrc=None),
            _make_track(title="Song C", provider_id="a3", provider="apple_music"),
        ]
        target_matched_isrc = _make_track(title="Song A", provider_id="t1")
        target_matched_fuzzy = _make_track(title="Song B", provider_id="t2")

        match_results = [
            MatchResult(source_track=source_tracks[0], matched_track=target_matched_isrc,
                        method="isrc", confidence=1.0),
            MatchResult(source_track=source_tracks[1], matched_track=target_matched_fuzzy,
                        method="fuzzy", confidence=0.85),
            MatchResult(source_track=source_tracks[2], matched_track=None,
                        method="none", confidence=0.0),
        ]

        source_provider = MagicMock()
        source_provider.is_authenticated.return_value = True
        source_provider.get_playlist_tracks.return_value = source_tracks
        source_provider.list_playlists.return_value = [
            _make_playlist(id="pl1", name="Mixed Playlist", provider="apple_music"),
        ]

        target_provider = MagicMock()
        target_provider.is_authenticated.return_value = True
        target_provider.create_playlist.return_value = _make_playlist(
            id="new_pl", name="Mixed Playlist", provider="tidal",
        )

        def _get_provider(name):
            if name == "apple_music":
                return MagicMock(return_value=source_provider)
            if name == "tidal":
                return MagicMock(return_value=target_provider)
            return None

        with patch("song_shift.cli.get_provider", side_effect=_get_provider), \
             patch("song_shift.cli.PlaylistMigrator") as mock_migrator_cls:
            mock_migrator = MagicMock()
            mock_migrator.matcher.match_tracks.return_value = match_results
            mock_migrator_cls.return_value = mock_migrator

            runner = CliRunner()
            result = runner.invoke(cli, [
                "migrate", "apple_music", "tidal", "--playlist-id", "pl1",
            ])

        assert result.exit_code == 0
        assert "2/3 tracks matched" in result.output
        assert "1 ISRC" in result.output
        assert "1 fuzzy" in result.output
        assert "1 unmatched" in result.output
        assert "Song C" in result.output
