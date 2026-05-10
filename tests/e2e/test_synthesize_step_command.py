from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import httpx
import numpy as np
import pytest
import respx
import soundfile as sf
from typer.testing import CliRunner

from polarsteps_tts.presentation.cli import app

_POLARSTEPS_BASE = "https://api.polarsteps.com"
_VOXTRAL_BASE = "http://localhost:8091"
_URL = "https://www.polarsteps.com/Alice/23964761-tour-mont-blanc"


def _trip_payload() -> dict[str, object]:
    return {
        "id": 23964761,
        "name": "Tour du Mont-Blanc",
        "start_date": 1721000000,
        "end_date": 1721800000,
        "user": {"first_name": "Alice"},
        "all_steps": [
            {
                "id": 1,
                "name": "Refuge des Mottets",
                "description": (
                    "Premier paragraphe du récit.\n\nDeuxième paragraphe avec un peu plus de texte."
                ),
                "start_time": 1721232000,
                "location": {"name": "Bourg-Saint-Maurice"},
            },
            {
                "id": 2,
                "name": "Step sans texte",
                "description": "",
                "start_time": 1721240000,
                "location": None,
            },
        ],
    }


def _silence_wav(sample_rate: int = 24000, duration_seconds: float = 0.5) -> bytes:
    samples = np.zeros(int(sample_rate * duration_seconds), dtype="int16")
    buffer = io.BytesIO()
    sf.write(buffer, samples, sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


@pytest.fixture
def runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    return CliRunner()


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    return tmp_path / "out"


@pytest.fixture
def no_sleep() -> Iterator[None]:
    """Skip retry backoff in case any test exercises a 5xx path."""
    with patch("polarsteps_tts.infrastructure.tts.voxtral.http_client.time.sleep"):
        yield


def _mock_happy_path() -> tuple[respx.Route, respx.Route, respx.Route]:
    trip_route = respx.get(f"{_POLARSTEPS_BASE}/trips/23964761").mock(
        return_value=httpx.Response(200, json=_trip_payload())
    )
    health_route = respx.get(f"{_VOXTRAL_BASE}/health").mock(return_value=httpx.Response(200))
    speech_route = respx.post(f"{_VOXTRAL_BASE}/v1/audio/speech").mock(
        return_value=httpx.Response(200, content=_silence_wav())
    )
    return trip_route, health_route, speech_route


class TestSynthesizeStepCommand:
    @respx.mock
    def test_writes_wav_file_for_step_with_text(self, runner: CliRunner, out_dir: Path) -> None:
        _mock_happy_path()

        result = runner.invoke(
            app,
            ["synthesize-step", _URL, "0", "--out", str(out_dir)],
        )

        assert result.exit_code == 0, result.output
        wav_files = list(out_dir.rglob("*.wav"))
        assert len(wav_files) == 1
        assert wav_files[0].stat().st_size > 0
        assert "Refuge des Mottets" in result.output

    @respx.mock
    def test_calls_tts_for_intro_and_each_paragraph(self, runner: CliRunner, out_dir: Path) -> None:
        _, _, speech_route = _mock_happy_path()

        result = runner.invoke(
            app,
            ["synthesize-step", _URL, "0", "--out", str(out_dir)],
        )

        assert result.exit_code == 0, result.output
        # 1 intro + 2 paragraphs in the fixture
        assert speech_route.call_count == 3

    @respx.mock
    def test_no_intro_skips_intro_call(self, runner: CliRunner, out_dir: Path) -> None:
        _, _, speech_route = _mock_happy_path()

        result = runner.invoke(
            app,
            ["synthesize-step", _URL, "0", "--out", str(out_dir), "--no-intro"],
        )

        assert result.exit_code == 0, result.output
        assert speech_route.call_count == 2  # body only, no intro

    @respx.mock
    def test_intro_text_includes_step_metadata(self, runner: CliRunner, out_dir: Path) -> None:
        _, _, speech_route = _mock_happy_path()

        result = runner.invoke(app, ["synthesize-step", _URL, "0", "--out", str(out_dir)])

        assert result.exit_code == 0, result.output
        intro_call = speech_route.calls[0].request
        body = intro_call.read().decode()
        assert "Étape 1" in body
        assert "Refuge des Mottets" in body
        assert "Bourg-Saint-Maurice" in body

    @respx.mock
    def test_caches_audio_on_second_run(self, runner: CliRunner, out_dir: Path) -> None:
        _, _, speech_route = _mock_happy_path()

        first = runner.invoke(
            app,
            ["synthesize-step", _URL, "0", "--out", str(out_dir)],
        )
        second = runner.invoke(
            app,
            ["synthesize-step", _URL, "0", "--out", str(out_dir)],
        )

        assert first.exit_code == 0
        assert second.exit_code == 0
        # Second run: trip cached + audio cached → no Voxtral calls
        assert speech_route.call_count == 3  # intro + 2 paragraphs (only first run)

    @respx.mock
    def test_no_tts_cache_disables_audio_cache(self, runner: CliRunner, out_dir: Path) -> None:
        _, _, speech_route = _mock_happy_path()

        runner.invoke(app, ["synthesize-step", _URL, "0", "--out", str(out_dir)])
        runner.invoke(app, ["synthesize-step", _URL, "0", "--out", str(out_dir), "--no-tts-cache"])

        # 3 calls (intro + 2 paragraphs) per run, 2 runs without cache
        assert speech_route.call_count == 6

    @respx.mock
    def test_unavailable_engine_exits_1(self, runner: CliRunner, out_dir: Path) -> None:
        respx.get(f"{_POLARSTEPS_BASE}/trips/23964761").mock(
            return_value=httpx.Response(200, json=_trip_payload())
        )
        respx.get(f"{_VOXTRAL_BASE}/health").mock(side_effect=httpx.ConnectError("nope"))

        result = runner.invoke(app, ["synthesize-step", _URL, "0", "--out", str(out_dir)])

        assert result.exit_code == 1
        assert "unreachable" in result.output.lower() or "error" in result.output.lower()

    def test_unknown_voice_exits_2(self, runner: CliRunner, out_dir: Path) -> None:
        result = runner.invoke(
            app,
            ["synthesize-step", _URL, "0", "--voice", "ghost_voice", "--out", str(out_dir)],
        )

        assert result.exit_code == 2
        assert "ghost_voice" in result.output

    @respx.mock
    def test_step_without_text_exits_1(self, runner: CliRunner, out_dir: Path) -> None:
        respx.get(f"{_POLARSTEPS_BASE}/trips/23964761").mock(
            return_value=httpx.Response(200, json=_trip_payload())
        )
        respx.get(f"{_VOXTRAL_BASE}/health").mock(return_value=httpx.Response(200))

        result = runner.invoke(app, ["synthesize-step", _URL, "1", "--out", str(out_dir)])

        assert result.exit_code == 1
        assert "no text" in result.output.lower()

    @respx.mock
    def test_step_index_out_of_range_exits_1(self, runner: CliRunner, out_dir: Path) -> None:
        respx.get(f"{_POLARSTEPS_BASE}/trips/23964761").mock(
            return_value=httpx.Response(200, json=_trip_payload())
        )
        respx.get(f"{_VOXTRAL_BASE}/health").mock(return_value=httpx.Response(200))

        result = runner.invoke(app, ["synthesize-step", _URL, "99", "--out", str(out_dir)])

        assert result.exit_code == 1
        assert "out of range" in result.output.lower()
