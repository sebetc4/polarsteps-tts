from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from polarsteps_tts.application.use_cases import (
    FetchTripCommand,
    FetchTripUseCase,
    PrepareNarrationCommand,
    PrepareNarrationUseCase,
    SynthesizeStepCommand,
    SynthesizeStepUseCase,
)
from polarsteps_tts.domain.entities import (
    AudioSegment,
    PresetVoice,
    Step,
    Trip,
    Voice,
)
from polarsteps_tts.domain.exceptions import DomainError
from polarsteps_tts.domain.ports import TextToSpeechEngine, TripRepository
from polarsteps_tts.domain.services import IntroGenerator, TextChunker, TextCleaner
from polarsteps_tts.domain.value_objects import Slug
from polarsteps_tts.infrastructure.polarsteps import parse_trip_url
from polarsteps_tts.infrastructure.storage import atomic_write_bytes

# n_decoding_steps=64 confirmed in 4.A smoke test; bumping this value at runtime
# (params.json edit) implies bumping this constant to invalidate the cache.
DEFAULT_MODEL_VERSION = "voxtral-4b-tts-2603-ndecsteps64"

# Inter-paragraph silence — confirmed mandatory in 4.A smoke test (masks voice
# variation between independent chunks). Étape 5 will own this for real.
INTER_CHUNK_SILENCE_SECONDS = 0.4


@dataclass(frozen=True, slots=True)
class SynthesizeStepArgs:
    url: str
    step_index: int
    voice: Voice
    out_dir: Path
    repository: TripRepository
    engine: TextToSpeechEngine
    include_intro: bool = True


@dataclass(frozen=True, slots=True)
class SynthesizeStepResult:
    out_path: Path
    step_name: str
    duration_seconds: float
    chunk_count: int


def synthesize_step(args: SynthesizeStepArgs) -> SynthesizeStepResult:
    """Resolve a step from a Polarsteps URL and synthesize it to a WAV file.

    Fail-fast on a TTS engine that's not ready (avoids burning 30s of HTTP
    work before discovering the server is down).
    """
    args.engine.health_check()

    trip_id, share_token = parse_trip_url(args.url)
    trip = FetchTripUseCase(args.repository).execute(FetchTripCommand(trip_id, share_token))
    step = _select_step(trip, args.step_index)

    prepare_uc = PrepareNarrationUseCase(
        intro_generator=IntroGenerator(),
        text_cleaner=TextCleaner(),
        text_chunker=TextChunker(),
    )
    script = prepare_uc.execute(
        PrepareNarrationCommand(step=step, include_intro=args.include_intro)
    )
    synthesized = SynthesizeStepUseCase(args.engine).execute(
        SynthesizeStepCommand(script=script, voice=args.voice)
    )

    out_path = _output_path(args.out_dir, trip, step, args.step_index)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _write_wav_with_silences(out_path, synthesized.segments, INTER_CHUNK_SILENCE_SECONDS)

    return SynthesizeStepResult(
        out_path=out_path,
        step_name=step.name,
        duration_seconds=synthesized.total_duration_seconds,
        chunk_count=len(synthesized.segments),
    )


def _select_step(trip: Trip, index: int) -> Step:
    if index < 0 or index >= len(trip.steps):
        raise DomainError(
            f"step_index {index} out of range: trip has {len(trip.steps)} steps (0..{len(trip.steps) - 1})"
        )
    return trip.steps[index]


def _output_path(root: Path, trip: Trip, step: Step, index: int) -> Path:
    trip_slug = Slug.from_text(trip.name)
    step_slug = Slug.from_text(step.name)
    return root / str(trip_slug) / f"{index:02d}_{step_slug}.wav"


def _write_wav_with_silences(
    path: Path,
    segments: tuple[AudioSegment, ...],
    silence_seconds: float,
) -> None:
    """Concatenate PCM segments with a fixed silence between them.

    Stop-gap until étape 5 takes over post-processing. Assumes all segments
    share the same sample rate and channel layout (true for Voxtral output).
    """
    if not segments:
        raise ValueError("Cannot write an empty audio file")

    sample_rate = segments[0].sample_rate
    channels = segments[0].channels
    if any(s.sample_rate != sample_rate or s.channels != channels for s in segments[1:]):
        raise ValueError(
            "Cannot concatenate segments with mismatched audio formats: "
            f"expected {sample_rate} Hz / {channels} ch"
        )
    silence_samples = int(sample_rate * silence_seconds)
    silence = np.zeros(silence_samples * channels, dtype="<i2")

    arrays: list[np.ndarray] = []
    for i, segment in enumerate(segments):
        arrays.append(np.frombuffer(segment.pcm, dtype="<i2"))
        if i < len(segments) - 1:
            arrays.append(silence)

    combined = np.concatenate(arrays)
    if channels > 1:
        combined = combined.reshape(-1, channels)

    buffer = io.BytesIO()
    sf.write(buffer, combined, sample_rate, format="WAV", subtype="PCM_16")
    atomic_write_bytes(path, buffer.getvalue())


def parse_voice(value: str) -> Voice:
    """Parse a CLI string into a `PresetVoice`, raising a clear error on miss."""
    try:
        return PresetVoice(value)
    except ValueError as e:
        valid = ", ".join(sorted(v.value for v in PresetVoice))
        raise DomainError(f"Unknown voice '{value}'. Available: {valid}") from e
