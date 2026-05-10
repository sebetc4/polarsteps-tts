from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console

from polarsteps_tts.application.use_cases import FetchTripCommand, FetchTripUseCase
from polarsteps_tts.domain.entities import Trip
from polarsteps_tts.domain.exceptions import DomainError
from polarsteps_tts.domain.ports import TripRepository
from polarsteps_tts.domain.services import FreshnessPolicy
from polarsteps_tts.infrastructure.cache import JsonFileCache
from polarsteps_tts.infrastructure.polarsteps import (
    CachedTripRepository,
    PolarstepsApiRepository,
    PolarstepsHttpClient,
    parse_trip_url,
)

app = typer.Typer(
    name="polarsteps-tts",
    help="Convert public Polarsteps trips to local TTS audio.",
    no_args_is_help=True,
)
_console = Console()


def _default_cache_root() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "polarsteps-tts" / "trips"


def _build_repository(no_cache: bool, refresh: bool) -> tuple[TripRepository, object]:
    """Return (repo, resource_to_close). Honors --no-cache and --refresh."""
    http_client = PolarstepsHttpClient()
    if no_cache:
        return PolarstepsApiRepository(http_client=http_client), http_client

    cache = JsonFileCache(_default_cache_root())
    if refresh:
        # Force a stale-equivalent cache by using a zero TTL policy.
        from datetime import timedelta

        freshness = FreshnessPolicy(ongoing_ttl=timedelta(0), finished_ttl=timedelta(0))
    else:
        freshness = FreshnessPolicy()

    return CachedTripRepository(
        http_client=http_client,
        cache=cache,
        freshness=freshness,
    ), http_client


@app.command()
def fetch(
    url: str = typer.Argument(..., help="Public Polarsteps trip URL."),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass the local cache entirely."),
    refresh: bool = typer.Option(
        False, "--refresh", help="Force a fresh fetch and overwrite the cache."
    ),
) -> None:
    """Fetch a public trip and print a summary to stdout."""
    try:
        trip_id, share_token = parse_trip_url(url)
    except DomainError as e:
        _console.print(f"[red]Invalid URL:[/red] {e}")
        raise typer.Exit(code=2) from e

    repository, owned = _build_repository(no_cache=no_cache, refresh=refresh)
    try:
        use_case = FetchTripUseCase(repository)
        trip = use_case.execute(FetchTripCommand(trip_id, share_token))
    except DomainError as e:
        _console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
    finally:
        if hasattr(owned, "close"):
            owned.close()

    _print_summary(trip)


def _print_summary(trip: Trip) -> None:
    with_text = trip.steps_with_text
    estimated_minutes = trip.total_text_length / 14 / 60  # ~14 chars/sec FR
    _console.print(f"[bold]{trip.name}[/bold]")
    if trip.author_first_name:
        _console.print(f"  Author: {trip.author_first_name}")
    _console.print(
        f"  Dates: {trip.start_date.date()} → {trip.end_date.date()}\n"
        f"  Steps: {len(trip.steps)} ({len(with_text)} with text)\n"
        f"  Total chars: {trip.total_text_length:,}\n"
        f"  Estimated audio: ~{estimated_minutes:.0f} min"
    )
