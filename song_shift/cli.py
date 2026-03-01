import click

import song_shift.providers  # noqa: F401 — register all providers
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
