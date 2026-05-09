from __future__ import annotations

import typer
from rich.console import Console

from polarsteps_tts.application.use_cases import FetchTripCommand, FetchTripUseCase
from polarsteps_tts.domain.entities import Trip
from polarsteps_tts.domain.exceptions import DomainError
from polarsteps_tts.infrastructure.polarsteps import PolarstepsApiRepository, parse_trip_url

app = typer.Typer(
    name="polarsteps-tts",
    help="Convert public Polarsteps trips to local TTS audio.",
    no_args_is_help=True,
)
_console = Console()


@app.command()
def fetch(
    url: str = typer.Argument(..., help="Public Polarsteps trip URL."),
) -> None:
    """Fetch a public trip and print a summary to stdout."""
    try:
        trip_id, share_token = parse_trip_url(url)
        with PolarstepsApiRepository() as repository:
            use_case = FetchTripUseCase(repository)
            trip = use_case.execute(FetchTripCommand(trip_id, share_token))
    except DomainError as e:
        _console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e

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
