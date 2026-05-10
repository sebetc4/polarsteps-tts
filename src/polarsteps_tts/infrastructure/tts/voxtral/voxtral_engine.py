from __future__ import annotations

import io

import numpy as np
import soundfile as sf

from polarsteps_tts.domain.entities import (
    AudioSegment,
    Language,
    Voice,
    voice_id,
)
from polarsteps_tts.domain.exceptions import (
    TtsEngineUnavailableError,
    TtsTextRejectedError,
)
from polarsteps_tts.domain.value_objects import DEFAULT_SYNTHESIS_OPTIONS, SynthesisOptions
from polarsteps_tts.infrastructure.tts.voxtral.http_client import VoxtralHttpClient


class VoxtralTtsEngine:
    """`TextToSpeechEngine` backed by a local Voxtral / vLLM-Omni server.

    Composes `VoxtralHttpClient` with a WAV->PCM conversion. Domain-side
    validation (empty text) happens here so the HTTP layer is never called
    for inputs we know are invalid.
    """

    def __init__(self, http_client: VoxtralHttpClient) -> None:
        self._http = http_client

    def synthesize(
        self,
        text: str,
        voice: Voice,
        language: Language = Language.FRENCH,
        options: SynthesisOptions = DEFAULT_SYNTHESIS_OPTIONS,
    ) -> AudioSegment:
        if not text.strip():
            raise TtsTextRejectedError("text is empty")

        wav_bytes = self._http.post_speech(
            text=text,
            voice=voice_id(voice),
            language=language.value,
            speed=options.speed,
            instructions=options.instructions,
            seed=options.seed,
        )
        return _wav_bytes_to_segment(wav_bytes)

    def health_check(self) -> None:
        if not self._http.is_alive():
            raise TtsEngineUnavailableError(f"Voxtral server unreachable at {self._http.base_url}")


def _wav_bytes_to_segment(wav_bytes: bytes) -> AudioSegment:
    """Decode WAV bytes into a 16-bit PCM segment.

    Voxtral returns 24 kHz mono int16 WAV. `soundfile.read(dtype="int16")`
    coerces unusual inputs into that representation, giving us a stable pivot.
    """
    arr, sample_rate = sf.read(io.BytesIO(wav_bytes), dtype="int16", always_2d=False)
    channels = 1 if arr.ndim == 1 else arr.shape[1]
    pcm: bytes = np.ascontiguousarray(arr).tobytes()
    return AudioSegment(pcm=pcm, sample_rate=int(sample_rate), channels=channels)
