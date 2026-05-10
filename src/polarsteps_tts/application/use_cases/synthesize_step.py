from __future__ import annotations

from dataclasses import dataclass

from polarsteps_tts.domain.entities import (
    AudioSegment,
    Language,
    NarrationScript,
    Voice,
)
from polarsteps_tts.domain.ports import TextToSpeechEngine
from polarsteps_tts.domain.value_objects import DEFAULT_SYNTHESIS_OPTIONS, SynthesisOptions


@dataclass(frozen=True, slots=True)
class SynthesizedStep:
    segments: tuple[AudioSegment, ...]
    voice_used: Voice
    total_duration_seconds: float


@dataclass(frozen=True, slots=True)
class SynthesizeStepCommand:
    script: NarrationScript
    voice: Voice
    language: Language = Language.FRENCH
    options: SynthesisOptions = DEFAULT_SYNTHESIS_OPTIONS


class SynthesizeStepUseCase:
    """Synthesize each chunk of a `NarrationScript` into an audio segment.

    The use case knows nothing about Voxtral or HTTP — it depends solely on
    the `TextToSpeechEngine` port. Concatenation and inter-chunk silences are
    deferred to étape 5 (post-processing).
    """

    def __init__(self, tts_engine: TextToSpeechEngine) -> None:
        self._tts = tts_engine

    def execute(self, command: SynthesizeStepCommand) -> SynthesizedStep:
        segments = tuple(
            self._tts.synthesize(chunk.text, command.voice, command.language, command.options)
            for chunk in command.script.chunks
        )
        total_duration = sum(s.duration_seconds for s in segments)
        return SynthesizedStep(
            segments=segments,
            voice_used=command.voice,
            total_duration_seconds=total_duration,
        )
