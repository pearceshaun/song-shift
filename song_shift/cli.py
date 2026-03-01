import click

import song_shift.providers  # noqa: F401 — register all providers
from song_shift.migrator import PlaylistMigrator
from song_shift.providers.base import get_provider, list_providers


@click.group()
def cli():
    """Song Shift — migrate playlists between music services."""
    pass


@cli.command()
@click.argument("provider_name")
def auth(provider_name: str):
    """Authenticate with a music service."""
    provider_cls = get_provider(provider_name)
    if provider_cls is None:
        available = ", ".join(list_providers())
        click.echo(
            click.style(
                f"Unknown provider: {provider_name}. Available: {available}",
                fg="red",
            )
        )
        raise SystemExit(1)

    provider = provider_cls()
    click.echo(f"Authenticating with {provider_name}...")
    provider.authenticate()
    click.echo(click.style(f"Authenticated with {provider_name}.", fg="green"))


@cli.command(name="list")
@click.argument("provider_name")
def list_cmd(provider_name: str):
    """List playlists from a music service."""
    provider_cls = get_provider(provider_name)
    if provider_cls is None:
        available = ", ".join(list_providers())
        click.echo(
            click.style(
                f"Unknown provider: {provider_name}. Available: {available}",
                fg="red",
            )
        )
        raise SystemExit(1)

    provider = provider_cls()
    if not provider.is_authenticated():
        click.echo(
            click.style(
                f"Not authenticated with {provider_name}. Run: song-shift auth {provider_name}",
                fg="red",
            )
        )
        raise SystemExit(1)

    playlists = provider.list_playlists()
    if not playlists:
        click.echo("No playlists found.")
        return

    for playlist in playlists:
        click.echo(f"  {playlist.name} ({playlist.track_count} tracks) [{playlist.id}]")


def _resolve_provider(name: str):
    """Resolve and validate a provider by name, exit on failure."""
    provider_cls = get_provider(name)
    if provider_cls is None:
        available = ", ".join(list_providers())
        click.echo(
            click.style(
                f"Unknown provider: {name}. Available: {available}",
                fg="red",
            )
        )
        raise SystemExit(1)
    provider = provider_cls()
    if not provider.is_authenticated():
        click.echo(
            click.style(
                f"Not authenticated with {name}. Run: song-shift auth {name}",
                fg="red",
            )
        )
        raise SystemExit(1)
    return provider


@cli.command()
@click.argument("source")
@click.argument("target")
@click.option("--playlist-id", required=True, help="ID of the playlist to migrate.")
@click.option("--playlist-name", default=None, help="Custom name for the created playlist.")
@click.option("--dry-run", is_flag=True, help="Show match results without creating the playlist.")
def migrate(source: str, target: str, playlist_id: str, playlist_name: str | None, dry_run: bool):
    """Migrate a playlist between music services."""
    source_provider = _resolve_provider(source)
    target_provider = _resolve_provider(target)

    click.echo(f"Fetching tracks from {source}...")
    source_tracks = source_provider.get_playlist_tracks(playlist_id)
    click.echo(f"Found {len(source_tracks)} tracks.")

    # Resolve playlist name from source if not provided
    if playlist_name is None:
        for pl in source_provider.list_playlists():
            if pl.id == playlist_id:
                playlist_name = pl.name
                break
        else:
            playlist_name = "Migrated Playlist"

    click.echo(f"Matching tracks on {target}...")
    migrator = PlaylistMigrator()
    match_results = migrator.matcher.match_tracks(source_tracks, target_provider)

    matched = [r for r in match_results if r.method != "none"]
    unmatched = [r for r in match_results if r.method == "none"]
    isrc_count = sum(1 for r in match_results if r.method == "isrc")
    fuzzy_count = sum(1 for r in match_results if r.method == "fuzzy")

    if dry_run:
        click.echo(click.style("\n[DRY RUN] No playlist created.", fg="yellow"))
    else:
        matched_track_ids = [r.matched_track.provider_id for r in matched]
        new_playlist = target_provider.create_playlist(playlist_name, "")
        if matched_track_ids:
            target_provider.add_tracks_to_playlist(new_playlist.id, matched_track_ids)
        click.echo(
            click.style(f"\nCreated playlist '{new_playlist.name}' on {target}.", fg="green")
        )

    # Summary
    click.echo(
        f"\n{len(matched)}/{len(source_tracks)} tracks matched "
        f"({isrc_count} ISRC, {fuzzy_count} fuzzy), "
        f"{len(unmatched)} unmatched"
    )

    if unmatched:
        click.echo("\nUnmatched tracks:")
        for r in unmatched:
            click.echo(f"  - {r.source_track}")
