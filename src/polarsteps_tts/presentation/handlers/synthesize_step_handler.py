from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import soundfile as sf
from mutagen.id3 import (  # type: ignore[attr-defined]
    ID3,
    TALB,
    TIT2,
    TPE1,
    TRCK,
    ID3NoHeaderError,
)

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
from polarsteps_tts.domain.value_objects import (
    DEFAULT_SYNTHESIS_OPTIONS,
    Slug,
    SynthesisOptions,
)
from polarsteps_tts.infrastructure.polarsteps import parse_trip_url
from polarsteps_tts.infrastructure.storage import atomic_write_bytes

TrackFormat = Literal["wav", "mp3"]
# OpenAI TTS API range — Voxtral inherits the same surface.
MIN_SPEED = 0.25
MAX_SPEED = 4.0
DEFAULT_SPEED = 1.0

# n_decoding_steps=64 confirmed in 4.A smoke test; bumping this value at runtime
# (params.json edit) implies bumping this constant to invalidate the cache.
DEFAULT_MODEL_VERSION = "voxtral-4b-tts-2603-ndecsteps64"

# Inter-paragraph silence — confirmed mandatory in 4.A smoke test (masks voice
# variation between independent chunks). Étape 5 will own this for real.
INTER_CHUNK_SILENCE_SECONDS = 0.4
# Padding silence at the very start and end of each track. Gives the player
# UX a clean intake before the intro and a graceful tail (avoids jarring
# cut-off when concatenating tracks downstream in étape 5).
LEADING_SILENCE_SECONDS = 0.5
TRAILING_SILENCE_SECONDS = 0.5


@dataclass(frozen=True, slots=True)
class SynthesizeStepArgs:
    url: str
    step_index: int
    voice: Voice
    out_dir: Path
    repository: TripRepository
    engine: TextToSpeechEngine
    include_intro: bool = True
    output_format: TrackFormat = "mp3"
    speed: float = DEFAULT_SPEED
    instructions: str | None = None


@dataclass(frozen=True, slots=True)
class SynthesizeStepResult:
    out_path: Path
    step_name: str
    duration_seconds: float
    chunk_count: int


@dataclass(frozen=True, slots=True)
class TrackMetadata:
    """ID3 tags written into MP3 outputs (no-op for WAV)."""

    title: str
    album: str | None = None
    artist: str | None = None
    track_number: int | None = None


def synthesize_step(args: SynthesizeStepArgs) -> SynthesizeStepResult:
    """Resolve a step from a Polarsteps URL and synthesize it to a WAV/MP3 file.

    Fail-fast on a TTS engine that's not ready (avoids burning 30s of HTTP
    work before discovering the server is down).
    """
    args.engine.health_check()

    trip_id, share_token = parse_trip_url(args.url)
    trip = FetchTripUseCase(args.repository).execute(FetchTripCommand(trip_id, share_token))
    step = _select_step(trip, args.step_index)

    return synthesize_resolved_step(
        trip=trip,
        step=step,
        index=args.step_index,
        engine=args.engine,
        voice=args.voice,
        out_dir=args.out_dir,
        include_intro=args.include_intro,
        output_format=args.output_format,
        speed=args.speed,
        instructions=args.instructions,
    )


def synthesize_resolved_step(
    *,
    trip: Trip,
    step: Step,
    index: int,
    engine: TextToSpeechEngine,
    voice: Voice,
    out_dir: Path,
    include_intro: bool = True,
    output_format: TrackFormat = "mp3",
    speed: float = DEFAULT_SPEED,
    instructions: str | None = None,
) -> SynthesizeStepResult:
    """Synthesize a step that has already been resolved from its trip.

    Shared core for `synthesize_step` (single-step CLI) and `synthesize_trip`
    (full-trip CLI). Skips the URL parsing + trip fetch + index lookup so the
    caller can amortise those over many steps.
    """
    prepare_uc = PrepareNarrationUseCase(
        intro_generator=IntroGenerator(),
        text_cleaner=TextCleaner(),
        text_chunker=TextChunker(),
    )
    script = prepare_uc.execute(PrepareNarrationCommand(step=step, include_intro=include_intro))
    if speed == DEFAULT_SPEED and instructions is None:
        options = DEFAULT_SYNTHESIS_OPTIONS
    else:
        options = SynthesisOptions(speed=speed, instructions=instructions)
    synthesized = SynthesizeStepUseCase(engine).execute(
        SynthesizeStepCommand(script=script, voice=voice, options=options)
    )

    out_path = _output_path(out_dir, trip, step, index, output_format)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = TrackMetadata(
        title=step.name or f"Étape {step.position}",
        album=trip.name,
        artist=trip.author_first_name,
        track_number=step.position,
    )
    _write_track(
        out_path,
        synthesized.segments,
        INTER_CHUNK_SILENCE_SECONDS,
        output_format=output_format,
        metadata=metadata,
    )

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


def _output_path(
    root: Path, trip: Trip, step: Step, index: int, output_format: TrackFormat = "mp3"
) -> Path:
    trip_slug = Slug.from_text(trip.name)
    step_slug = Slug.from_text(step.name)
    return root / str(trip_slug) / f"{index:02d}_{step_slug}.{output_format}"


# soundfile compression_level for MP3 in [0.0, 1.0] (lower = better quality).
# 0.2 ≈ LAME `qscale 2` (high-quality VBR), the value declared in CLAUDE.md.
_MP3_COMPRESSION_LEVEL = 0.2


def _write_track(
    path: Path,
    segments: tuple[AudioSegment, ...],
    silence_seconds: float,
    *,
    output_format: TrackFormat = "mp3",
    metadata: TrackMetadata | None = None,
    leading_silence_seconds: float = LEADING_SILENCE_SECONDS,
    trailing_silence_seconds: float = TRAILING_SILENCE_SECONDS,
) -> None:
    """Concatenate PCM segments with silence padding and encode as WAV or MP3.

    All segments must share sample rate / channel layout (always true for
    Voxtral output). For MP3, ID3 tags are written from `metadata` after the
    audio stream is committed.
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

    def _silence(seconds: float) -> np.ndarray:
        samples = int(sample_rate * seconds)
        return np.zeros(samples * channels, dtype="<i2")

    inter_silence = _silence(silence_seconds)
    arrays: list[np.ndarray] = [_silence(leading_silence_seconds)]
    for i, segment in enumerate(segments):
        arrays.append(np.frombuffer(segment.pcm, dtype="<i2"))
        if i < len(segments) - 1:
            arrays.append(inter_silence)
    arrays.append(_silence(trailing_silence_seconds))

    combined = np.concatenate(arrays)
    if channels > 1:
        combined = combined.reshape(-1, channels)

    buffer = io.BytesIO()
    if output_format == "mp3":
        sf.write(
            buffer,
            combined,
            sample_rate,
            format="MP3",
            subtype="MPEG_LAYER_III",
            compression_level=_MP3_COMPRESSION_LEVEL,
        )
    else:
        sf.write(buffer, combined, sample_rate, format="WAV", subtype="PCM_16")
    atomic_write_bytes(path, buffer.getvalue())

    if output_format == "mp3" and metadata is not None:
        _write_id3_tags(path, metadata)


def _write_id3_tags(path: Path, metadata: TrackMetadata) -> None:
    """Attach ID3v2 tags to an MP3 file written by `_write_track`."""
    # mutagen exposes ID3 frames as runtime-defined classes — mypy can't follow
    # the constructors. We type-ignore call-by-call rather than at module level
    # so other potential mutagen issues still surface.
    try:
        tags = ID3(str(path))  # type: ignore[no-untyped-call]
    except ID3NoHeaderError:
        tags = ID3()  # type: ignore[no-untyped-call]
    tags.add(TIT2(encoding=3, text=metadata.title))  # type: ignore[no-untyped-call]
    if metadata.album:
        tags.add(TALB(encoding=3, text=metadata.album))  # type: ignore[no-untyped-call]
    if metadata.artist:
        tags.add(TPE1(encoding=3, text=metadata.artist))  # type: ignore[no-untyped-call]
    if metadata.track_number is not None:
        tags.add(  # type: ignore[no-untyped-call]
            TRCK(encoding=3, text=str(metadata.track_number))  # type: ignore[no-untyped-call]
        )
    tags.save(str(path))


def parse_voice(value: str) -> Voice:
    """Parse a CLI string into a `PresetVoice`, raising a clear error on miss."""
    try:
        return PresetVoice(value)
    except ValueError as e:
        valid = ", ".join(sorted(v.value for v in PresetVoice))
        raise DomainError(f"Unknown voice '{value}'. Available: {valid}") from e
