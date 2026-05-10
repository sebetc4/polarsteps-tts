from __future__ import annotations

import io
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import httpx
import numpy as np
import pytest
import respx
import soundfile as sf

from polarsteps_tts.domain.exceptions import TtsEngineError, TtsTextRejectedError
from polarsteps_tts.infrastructure.tts.voxtral import VoxtralHttpClient

_BASE = "http://localhost:8091"
_SPEECH_URL = f"{_BASE}/v1/audio/speech"
_HEALTH_URL = f"{_BASE}/health"


def _silence_wav(sample_rate: int = 24000, duration_seconds: float = 0.1) -> bytes:
    """Return minimal valid WAV bytes for tests (silence)."""
    samples = np.zeros(int(sample_rate * duration_seconds), dtype="int16")
    buffer = io.BytesIO()
    sf.write(buffer, samples, sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


@pytest.fixture
def no_sleep() -> Iterator[None]:
    """Speed up retry tests by no-oping the backoff sleep."""
    with patch("polarsteps_tts.infrastructure.tts.voxtral.http_client.time.sleep"):
        yield


class TestVoxtralHttpClientPostSpeech:
    @respx.mock
    def test_returns_wav_bytes_on_200(self) -> None:
        wav = _silence_wav()
        respx.post(_SPEECH_URL).mock(
            return_value=httpx.Response(200, content=wav, headers={"Content-Type": "audio/wav"})
        )
        with VoxtralHttpClient() as client:
            result = client.post_speech("Bonjour", voice="fr_female")
        assert result == wav

    @respx.mock
    def test_payload_includes_required_fields(self) -> None:
        captured: dict[str, Any] = {}

        def _capture(request: httpx.Request) -> httpx.Response:
            import json

            captured.update(json.loads(request.content))
            return httpx.Response(200, content=_silence_wav())

        respx.post(_SPEECH_URL).mock(side_effect=_capture)
        with VoxtralHttpClient(model="my/model") as client:
            client.post_speech("Bonjour", voice="fr_male", language="fr", speed=0.95, seed=42)

        assert captured["input"] == "Bonjour"
        assert captured["voice"] == "fr_male"
        assert captured["model"] == "my/model"
        assert captured["language"] == "fr"
        assert captured["speed"] == 0.95
        assert captured["response_format"] == "wav"
        assert captured["seed"] == 42

    @respx.mock
    def test_omits_optional_fields_when_unset(self) -> None:
        captured: dict[str, Any] = {}

        def _capture(request: httpx.Request) -> httpx.Response:
            import json

            captured.update(json.loads(request.content))
            return httpx.Response(200, content=_silence_wav())

        respx.post(_SPEECH_URL).mock(side_effect=_capture)
        with VoxtralHttpClient() as client:
            client.post_speech("Bonjour", voice="fr_female")

        assert "instructions" not in captured
        assert "seed" not in captured

    @respx.mock
    def test_4xx_raises_tts_text_rejected_no_retry(self) -> None:
        route = respx.post(_SPEECH_URL).mock(
            return_value=httpx.Response(400, json={"error": "voice not found"})
        )
        with VoxtralHttpClient() as client, pytest.raises(TtsTextRejectedError):
            client.post_speech("Bonjour", voice="ghost_voice")
        assert route.call_count == 1  # no retry on 4xx

    @respx.mock
    def test_5xx_retries_then_raises_tts_engine_error(self, no_sleep: None) -> None:
        route = respx.post(_SPEECH_URL).mock(
            return_value=httpx.Response(503, json={"error": "overloaded"})
        )
        with VoxtralHttpClient() as client, pytest.raises(TtsEngineError):
            client.post_speech("Bonjour", voice="fr_female")
        assert route.call_count == 3

    @respx.mock
    def test_5xx_then_200_succeeds_within_retries(self, no_sleep: None) -> None:
        wav = _silence_wav()
        route = respx.post(_SPEECH_URL).mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, content=wav),
            ]
        )
        with VoxtralHttpClient() as client:
            result = client.post_speech("Bonjour", voice="fr_female")
        assert result == wav
        assert route.call_count == 2

    @respx.mock
    def test_connect_error_retries_then_raises_tts_engine_error(self, no_sleep: None) -> None:
        route = respx.post(_SPEECH_URL).mock(side_effect=httpx.ConnectError("nope"))
        with VoxtralHttpClient() as client, pytest.raises(TtsEngineError):
            client.post_speech("Bonjour", voice="fr_female")
        assert route.call_count == 3


class TestVoxtralHttpClientHealth:
    @respx.mock
    def test_is_alive_true_on_200(self) -> None:
        respx.get(_HEALTH_URL).mock(return_value=httpx.Response(200))
        with VoxtralHttpClient() as client:
            assert client.is_alive() is True

    @respx.mock
    def test_is_alive_false_on_500(self) -> None:
        respx.get(_HEALTH_URL).mock(return_value=httpx.Response(500))
        with VoxtralHttpClient() as client:
            assert client.is_alive() is False

    @respx.mock
    def test_is_alive_false_on_connect_error_does_not_raise(self) -> None:
        respx.get(_HEALTH_URL).mock(side_effect=httpx.ConnectError("nope"))
        with VoxtralHttpClient() as client:
            assert client.is_alive() is False
