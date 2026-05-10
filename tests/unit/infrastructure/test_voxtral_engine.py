from __future__ import annotations

import io
from unittest.mock import MagicMock

import numpy as np
import pytest
import soundfile as sf

from polarsteps_tts.domain.entities import CustomVoice, PresetVoice
from polarsteps_tts.domain.exceptions import (
    TtsEngineError,
    TtsEngineUnavailableError,
    TtsTextRejectedError,
)
from polarsteps_tts.domain.value_objects import SynthesisOptions
from polarsteps_tts.infrastructure.tts.voxtral import VoxtralHttpClient, VoxtralTtsEngine


def _make_wav(sample_rate: int = 24000, duration_seconds: float = 0.5) -> bytes:
    samples = np.zeros(int(sample_rate * duration_seconds), dtype="int16")
    buffer = io.BytesIO()
    sf.write(buffer, samples, sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def _make_http_client_mock(*, wav_bytes: bytes | None = None, alive: bool = True) -> MagicMock:
    mock = MagicMock(spec=VoxtralHttpClient)
    mock.base_url = "http://localhost:8091"
    mock.is_alive.return_value = alive
    if wav_bytes is not None:
        mock.post_speech.return_value = wav_bytes
    return mock


class TestVoxtralTtsEngineSynthesize:
    def test_returns_audio_segment_with_correct_metadata(self) -> None:
        http = _make_http_client_mock(wav_bytes=_make_wav(sample_rate=24000, duration_seconds=1.0))
        engine = VoxtralTtsEngine(http_client=http)

        segment = engine.synthesize("Bonjour", PresetVoice.FR_FEMALE)

        assert segment.sample_rate == 24000
        assert segment.channels == 1
        assert segment.duration_seconds == pytest.approx(1.0, abs=0.01)

    def test_empty_text_raises_without_calling_http(self) -> None:
        http = _make_http_client_mock(wav_bytes=_make_wav())
        engine = VoxtralTtsEngine(http_client=http)

        with pytest.raises(TtsTextRejectedError):
            engine.synthesize("   ", PresetVoice.FR_FEMALE)

        http.post_speech.assert_not_called()

    def test_passes_preset_voice_value_to_http_client(self) -> None:
        http = _make_http_client_mock(wav_bytes=_make_wav())
        engine = VoxtralTtsEngine(http_client=http)

        engine.synthesize("Bonjour", PresetVoice.FR_MALE)

        assert http.post_speech.call_args.kwargs["voice"] == "fr_male"

    def test_passes_custom_voice_name_to_http_client(self) -> None:
        http = _make_http_client_mock(wav_bytes=_make_wav())
        engine = VoxtralTtsEngine(http_client=http)

        engine.synthesize("Bonjour", CustomVoice(name="my_clone"))

        assert http.post_speech.call_args.kwargs["voice"] == "my_clone"

    def test_passes_synthesis_options_to_http_client(self) -> None:
        http = _make_http_client_mock(wav_bytes=_make_wav())
        engine = VoxtralTtsEngine(http_client=http)

        options = SynthesisOptions(instructions="warm tone", speed=0.95, seed=42)
        engine.synthesize("Bonjour", PresetVoice.FR_FEMALE, options=options)

        kwargs = http.post_speech.call_args.kwargs
        assert kwargs["instructions"] == "warm tone"
        assert kwargs["speed"] == 0.95
        assert kwargs["seed"] == 42

    def test_propagates_tts_engine_error_from_http_client(self) -> None:
        http = _make_http_client_mock()
        http.post_speech.side_effect = TtsEngineError("upstream went bad")
        engine = VoxtralTtsEngine(http_client=http)

        with pytest.raises(TtsEngineError):
            engine.synthesize("Bonjour", PresetVoice.FR_FEMALE)


class TestVoxtralTtsEngineHealthCheck:
    def test_passes_when_http_client_is_alive(self) -> None:
        engine = VoxtralTtsEngine(http_client=_make_http_client_mock(alive=True))
        engine.health_check()

    def test_raises_unavailable_when_http_client_is_dead(self) -> None:
        engine = VoxtralTtsEngine(http_client=_make_http_client_mock(alive=False))
        with pytest.raises(TtsEngineUnavailableError):
            engine.health_check()
