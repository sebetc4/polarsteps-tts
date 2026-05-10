from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console

from polarsteps_tts.application.use_cases import FetchTripCommand, FetchTripUseCase
from polarsteps_tts.domain.entities import Trip
from polarsteps_tts.domain.exceptions import DomainError
from polarsteps_tts.domain.ports import TextToSpeechEngine, TripRepository
from polarsteps_tts.domain.services import FreshnessPolicy
from polarsteps_tts.infrastructure.cache import JsonFileCache, WavFileAudioSegmentCache
from polarsteps_tts.infrastructure.polarsteps import (
    CachedTripRepository,
    PolarstepsApiRepository,
    PolarstepsHttpClient,
    parse_trip_url,
)
from polarsteps_tts.infrastructure.tts import CachingTextToSpeechEngine
from polarsteps_tts.infrastructure.tts.voxtral import (
    DEFAULT_BASE_URL,
    VoxtralHttpClient,
    VoxtralTtsEngine,
)
from polarsteps_tts.presentation.handlers import (
    DEFAULT_MODEL_VERSION,
    SynthesizeStepArgs,
    parse_voice,
    synthesize_step,
)

app = typer.Typer(
    name="polarsteps-tts",
    help="Convert public Polarsteps trips to local TTS audio.",
    no_args_is_help=True,
)
_console = Console()

_DEFAULT_OUT_DIR = Path("./out")


def _default_trip_cache_root() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "polarsteps-tts" / "trips"


def _default_audio_cache_root() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "polarsteps-tts" / "audio"


def _build_repository(no_cache: bool, refresh: bool) -> tuple[TripRepository, object]:
    """Return (repo, resource_to_close). Honors --no-cache and --refresh."""
    http_client = PolarstepsHttpClient()
    if no_cache:
        return PolarstepsApiRepository(http_client=http_client), http_client

    cache = JsonFileCache(_default_trip_cache_root())
    if refresh:
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


@app.command(name="synthesize-step")
def synthesize_step_cmd(
    url: str = typer.Argument(..., help="Public Polarsteps trip URL."),
    step_index: int = typer.Argument(..., help="0-based index of the step to synthesize."),
    voice: str = typer.Option("fr_female", "--voice", help="Voice preset id (e.g. fr_female)."),
    out: Path = typer.Option(_DEFAULT_OUT_DIR, "--out", help="Output WAV directory."),
    voxtral_url: str = typer.Option(
        DEFAULT_BASE_URL, "--voxtral-url", help="Base URL of the local Voxtral server."
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass the trip payload cache."),
    refresh: bool = typer.Option(
        False, "--refresh", help="Force a fresh trip fetch and overwrite the cache."
    ),
    no_tts_cache: bool = typer.Option(
        False, "--no-tts-cache", help="Bypass the audio segment cache (always re-synthesize)."
    ),
    no_intro: bool = typer.Option(
        False, "--no-intro", help="Skip the spoken intro ('Étape N : ...') before the body."
    ),
) -> None:
    """Synthesize a single step's text into a WAV audio file."""
    try:
        parsed_voice = parse_voice(voice)
    except DomainError as e:
        _console.print(f"[red]Invalid voice:[/red] {e}")
        raise typer.Exit(code=2) from e

    repository, owned_http = _build_repository(no_cache=no_cache, refresh=refresh)
    voxtral_http = VoxtralHttpClient(base_url=voxtral_url)
    engine: TextToSpeechEngine = VoxtralTtsEngine(http_client=voxtral_http)

    if not no_tts_cache:
        audio_cache = WavFileAudioSegmentCache(_default_audio_cache_root())
        engine = CachingTextToSpeechEngine(
            inner=engine,
            cache=audio_cache,
            model_version=DEFAULT_MODEL_VERSION,
        )

    try:
        result = synthesize_step(
            SynthesizeStepArgs(
                url=url,
                step_index=step_index,
                voice=parsed_voice,
                out_dir=out,
                repository=repository,
                engine=engine,
                include_intro=not no_intro,
            )
        )
    except DomainError as e:
        _console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
    finally:
        if hasattr(owned_http, "close"):
            owned_http.close()
        voxtral_http.close()

    _console.print(
        f"[green]✓[/green] {result.step_name}\n"
        f"  Output: {result.out_path}\n"
        f"  Chunks: {result.chunk_count}\n"
        f"  Duration: {result.duration_seconds:.1f}s"
    )


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
