from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from polarsteps_tts.application.use_cases import FetchTripCommand, FetchTripUseCase
from polarsteps_tts.domain.entities import Step, Trip, Voice
from polarsteps_tts.domain.exceptions import DomainError
from polarsteps_tts.domain.ports import TextToSpeechEngine, TripRepository
from polarsteps_tts.infrastructure.polarsteps import parse_trip_url
from polarsteps_tts.presentation.handlers.synthesize_step_handler import (
    SynthesizeStepResult,
    TrackFormat,
    synthesize_resolved_step,
)


@dataclass(frozen=True, slots=True)
class SynthesizeTripArgs:
    url: str
    voice: Voice
    out_dir: Path
    repository: TripRepository
    engine: TextToSpeechEngine
    include_intro: bool = True
    output_format: TrackFormat = "mp3"
    # Optional callback invoked once per step (after success or failure) so the
    # CLI can drive a progress bar without coupling the handler to `rich`.
    on_step_done: Callable[[Step, SynthesizeStepResult | None, Exception | None], None] | None = (
        None
    )


@dataclass(frozen=True, slots=True)
class SynthesizeTripFailure:
    step: Step
    error: Exception


@dataclass(frozen=True, slots=True)
class SynthesizeTripResult:
    trip: Trip
    successes: tuple[SynthesizeStepResult, ...] = field(default_factory=tuple)
    failures: tuple[SynthesizeTripFailure, ...] = field(default_factory=tuple)

    @property
    def total_duration_seconds(self) -> float:
        return sum(r.duration_seconds for r in self.successes)


def synthesize_trip(args: SynthesizeTripArgs) -> SynthesizeTripResult:
    """Synthesize every narratable step of a Polarsteps trip in order.

    Continues on per-step failure (collected in `failures`) so an audiobook
    run is not aborted by one bad step. Fails fast only if the TTS engine is
    unreachable upfront.
    """
    args.engine.health_check()

    trip_id, share_token = parse_trip_url(args.url)
    trip = FetchTripUseCase(args.repository).execute(FetchTripCommand(trip_id, share_token))

    successes: list[SynthesizeStepResult] = []
    failures: list[SynthesizeTripFailure] = []

    for step in trip.steps_with_text:
        # The 0-based step_index aligns with how `synthesize-step` numbers
        # output files (00_, 01_, ...): we use the position in `trip.steps`
        # so silent steps still consume their slot.
        index = trip.steps.index(step)
        try:
            result = synthesize_resolved_step(
                trip=trip,
                step=step,
                index=index,
                engine=args.engine,
                voice=args.voice,
                out_dir=args.out_dir,
                include_intro=args.include_intro,
                output_format=args.output_format,
            )
        except (DomainError, OSError) as e:
            failures.append(SynthesizeTripFailure(step=step, error=e))
            if args.on_step_done is not None:
                args.on_step_done(step, None, e)
            continue
        successes.append(result)
        if args.on_step_done is not None:
            args.on_step_done(step, result, None)

    return SynthesizeTripResult(
        trip=trip,
        successes=tuple(successes),
        failures=tuple(failures),
    )
