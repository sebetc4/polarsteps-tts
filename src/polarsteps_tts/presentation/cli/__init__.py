from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)

from polarsteps_tts.application.use_cases import FetchTripCommand, FetchTripUseCase
from polarsteps_tts.domain.entities import Trip
from polarsteps_tts.domain.exceptions import DomainError
from polarsteps_tts.domain.ports import TextToSpeechEngine, TripRepository
from polarsteps_tts.domain.services import AudioEstimator, FreshnessPolicy
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
    SynthesizeTripArgs,
    parse_voice,
    synthesize_step,
    synthesize_trip,
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


@contextmanager
def _build_repository(no_cache: bool, refresh: bool) -> Iterator[TripRepository]:
    """Yield a configured TripRepository and close the underlying HTTP client on exit."""
    with PolarstepsHttpClient() as http_client:
        if no_cache:
            yield PolarstepsApiRepository(http_client=http_client)
            return

        cache = JsonFileCache(_default_trip_cache_root())
        freshness = (
            FreshnessPolicy(ongoing_ttl=timedelta(0), finished_ttl=timedelta(0))
            if refresh
            else FreshnessPolicy()
        )
        yield CachedTripRepository(
            http_client=http_client,
            cache=cache,
            freshness=freshness,
        )


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

    try:
        with _build_repository(no_cache=no_cache, refresh=refresh) as repository:
            trip = FetchTripUseCase(repository).execute(FetchTripCommand(trip_id, share_token))
    except DomainError as e:
        _console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e

    _print_summary(trip)


@app.command(name="synthesize-step")
def synthesize_step_cmd(
    url: str = typer.Argument(..., help="Public Polarsteps trip URL."),
    step_index: int = typer.Argument(..., help="0-based index of the step to synthesize."),
    voice: str = typer.Option("fr_female", "--voice", help="Voice preset id (e.g. fr_female)."),
    out: Path = typer.Option(_DEFAULT_OUT_DIR, "--out", help="Output directory."),
    output_format: str = typer.Option(
        "mp3", "--format", help="Output audio format: 'mp3' (with ID3 tags) or 'wav'."
    ),
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
    """Synthesize a single step's text into an audio file (MP3 by default)."""
    if output_format not in ("mp3", "wav"):
        _console.print(f"[red]Invalid format:[/red] '{output_format}' (expected 'mp3' or 'wav')")
        raise typer.Exit(code=2)
    try:
        parsed_voice = parse_voice(voice)
    except DomainError as e:
        _console.print(f"[red]Invalid voice:[/red] {e}")
        raise typer.Exit(code=2) from e

    try:
        with (
            _build_repository(no_cache=no_cache, refresh=refresh) as repository,
            VoxtralHttpClient(base_url=voxtral_url) as voxtral_http,
        ):
            engine: TextToSpeechEngine = VoxtralTtsEngine(http_client=voxtral_http)
            if not no_tts_cache:
                audio_cache = WavFileAudioSegmentCache(_default_audio_cache_root())
                engine = CachingTextToSpeechEngine(
                    inner=engine,
                    cache=audio_cache,
                    model_version=DEFAULT_MODEL_VERSION,
                )

            result = synthesize_step(
                SynthesizeStepArgs(
                    url=url,
                    step_index=step_index,
                    voice=parsed_voice,
                    out_dir=out,
                    repository=repository,
                    engine=engine,
                    include_intro=not no_intro,
                    output_format=output_format,  # type: ignore[arg-type]
                )
            )
    except DomainError as e:
        _console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e

    _console.print(
        f"[green]✓[/green] {result.step_name}\n"
        f"  Output: {result.out_path}\n"
        f"  Chunks: {result.chunk_count}\n"
        f"  Duration: {result.duration_seconds:.1f}s"
    )


@app.command(name="synthesize-trip")
def synthesize_trip_cmd(
    url: str = typer.Argument(..., help="Public Polarsteps trip URL."),
    voice: str = typer.Option("fr_female", "--voice", help="Voice preset id (e.g. fr_female)."),
    out: Path = typer.Option(_DEFAULT_OUT_DIR, "--out", help="Output directory."),
    output_format: str = typer.Option(
        "mp3", "--format", help="Output audio format: 'mp3' (with ID3 tags) or 'wav'."
    ),
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
        False, "--no-intro", help="Skip the spoken intro before each step's body."
    ),
) -> None:
    """Synthesize every narratable step of a trip into per-step audio files."""
    if output_format not in ("mp3", "wav"):
        _console.print(f"[red]Invalid format:[/red] '{output_format}' (expected 'mp3' or 'wav')")
        raise typer.Exit(code=2)
    try:
        parsed_voice = parse_voice(voice)
    except DomainError as e:
        _console.print(f"[red]Invalid voice:[/red] {e}")
        raise typer.Exit(code=2) from e

    try:
        with (
            _build_repository(no_cache=no_cache, refresh=refresh) as repository,
            VoxtralHttpClient(base_url=voxtral_url) as voxtral_http,
            Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
                console=_console,
                transient=False,
            ) as progress,
        ):
            engine: TextToSpeechEngine = VoxtralTtsEngine(http_client=voxtral_http)
            if not no_tts_cache:
                audio_cache = WavFileAudioSegmentCache(_default_audio_cache_root())
                engine = CachingTextToSpeechEngine(
                    inner=engine,
                    cache=audio_cache,
                    model_version=DEFAULT_MODEL_VERSION,
                )

            task_id: list[TaskID] = []  # mutable closure cell

            def on_step_done(step, result, error):  # type: ignore[no-untyped-def]
                if not task_id:
                    return
                if error is not None:
                    progress.console.print(
                        f"[red]✗[/red] step {step.position} '{step.name}': {error}"
                    )
                else:
                    progress.console.print(
                        f"[green]✓[/green] step {step.position} '{step.name}' "
                        f"({result.duration_seconds:.0f}s, {result.chunk_count} chunks)"
                    )
                progress.advance(task_id[0])

            args = SynthesizeTripArgs(
                url=url,
                voice=parsed_voice,
                out_dir=out,
                repository=repository,
                engine=engine,
                include_intro=not no_intro,
                output_format=output_format,  # type: ignore[arg-type]
                on_step_done=on_step_done,
            )
            # Probe the engine once before adding the progress task so a Voxtral
            # outage surfaces as a single error line, not a stalled bar.
            engine.health_check()
            trip_id, share_token = parse_trip_url(url)
            trip = FetchTripUseCase(repository).execute(FetchTripCommand(trip_id, share_token))
            task = progress.add_task(f"[cyan]{trip.name}[/cyan]", total=len(trip.steps_with_text))
            task_id.append(task)
            # Re-run the full handler now that the trip is cached locally
            # (cheap second fetch served from cache).
            result = synthesize_trip(args)
    except DomainError as e:
        _console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e

    _console.print(
        f"\n[bold green]Done.[/bold green] {len(result.successes)}/"
        f"{len(result.successes) + len(result.failures)} steps synthesized "
        f"({result.total_duration_seconds / 60:.1f} min total audio)."
    )
    if result.failures:
        _console.print(f"[red]{len(result.failures)} failures:[/red]")
        for fail in result.failures:
            _console.print(f"  step {fail.step.position} '{fail.step.name}': {fail.error}")
        raise typer.Exit(code=1)


def _print_summary(trip: Trip) -> None:
    with_text = trip.steps_with_text
    estimated = AudioEstimator().estimate(trip)
    end_label = trip.end_date.date().isoformat() if trip.end_date else "en cours"
    _console.print(f"[bold]{trip.name}[/bold]")
    if trip.author_first_name:
        _console.print(f"  Author: {trip.author_first_name}")
    _console.print(
        f"  Dates: {trip.start_date.date()} → {end_label}\n"
        f"  Steps: {len(trip.steps)} ({len(with_text)} with text)\n"
        f"  Total chars: {trip.total_text_length:,}\n"
        f"  Estimated audio: ~{estimated.minutes:.0f} min"
    )
