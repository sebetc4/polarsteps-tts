from __future__ import annotations

from typing import Protocol

from polarsteps_tts.domain.entities.audio_segment import AudioSegment
from polarsteps_tts.domain.entities.language import Language
from polarsteps_tts.domain.entities.voice import Voice
from polarsteps_tts.domain.value_objects.synthesis_options import (
    DEFAULT_SYNTHESIS_OPTIONS,
    SynthesisOptions,
)


class TextToSpeechEngine(Protocol):
    """Synthesizes text into a single audio segment.

    Stateless from the domain's point of view: callers handle batching and
    chunk concatenation. Implementations translate transport/model errors
    into `TtsEngineError` / `TtsTextRejectedError` at the boundary.
    """

    def synthesize(
        self,
        text: str,
        voice: Voice,
        language: Language = Language.FRENCH,
        options: SynthesisOptions = DEFAULT_SYNTHESIS_OPTIONS,
    ) -> AudioSegment: ...

    def health_check(self) -> None:
        """Raise `TtsEngineUnavailableError` if the engine cannot serve requests."""
        ...
