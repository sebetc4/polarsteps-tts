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
                "description": "Premier paragraphe.\n\nDeuxième paragraphe.",
                "start_time": 1721232000,
                "location": {"name": "Bourg-Saint-Maurice"},
            },
            {
                "id": 2,
                "name": "Step muet",
                "description": "",
                "start_time": 1721240000,
                "location": None,
            },
            {
                "id": 3,
                "name": "Col de la Seigne",
                "description": "Texte du troisième step.",
                "start_time": 1721250000,
                "location": {"name": "Col de la Seigne"},
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


class TestSynthesizeTripCommand:
    @respx.mock
    def test_synthesizes_all_steps_with_text_as_wav(self, runner: CliRunner, out_dir: Path) -> None:
        _mock_happy_path()

        result = runner.invoke(
            app, ["synthesize-trip", _URL, "--out", str(out_dir), "--format", "wav"]
        )

        assert result.exit_code == 0, result.output
        wav_files = sorted(out_dir.rglob("*.wav"))
        # 2 steps with text out of 3 (step 2 is muet)
        assert len(wav_files) == 2
        # File names follow the index in trip.steps (00, 02), skipping the silent one.
        names = [f.name for f in wav_files]
        assert names[0].startswith("00_")
        assert names[1].startswith("02_")

    @respx.mock
    def test_default_output_is_mp3_with_id3_tags(self, runner: CliRunner, out_dir: Path) -> None:
        from mutagen.id3 import ID3

        _mock_happy_path()

        result = runner.invoke(app, ["synthesize-trip", _URL, "--out", str(out_dir)])

        assert result.exit_code == 0, result.output
        mp3_files = sorted(out_dir.rglob("*.mp3"))
        assert len(mp3_files) == 2
        first = ID3(str(mp3_files[0]))
        assert first["TALB"].text[0] == "Tour du Mont-Blanc"
        assert first["TPE1"].text[0] == "Alice"
        # First step is at position 1, second at position 3.
        assert first["TRCK"].text[0] == "1"
        second = ID3(str(mp3_files[1]))
        assert second["TRCK"].text[0] == "3"

    @respx.mock
    def test_summary_reports_success_count(self, runner: CliRunner, out_dir: Path) -> None:
        _mock_happy_path()

        result = runner.invoke(app, ["synthesize-trip", _URL, "--out", str(out_dir)])

        assert result.exit_code == 0
        assert "2/2 steps synthesized" in result.output

    @respx.mock
    def test_unknown_voice_exits_2(self, runner: CliRunner, out_dir: Path) -> None:
        result = runner.invoke(
            app,
            ["synthesize-trip", _URL, "--voice", "ghost_voice", "--out", str(out_dir)],
        )

        assert result.exit_code == 2
        assert "ghost_voice" in result.output

    @respx.mock
    def test_unavailable_engine_exits_1(self, runner: CliRunner, out_dir: Path) -> None:
        respx.get(f"{_POLARSTEPS_BASE}/trips/23964761").mock(
            return_value=httpx.Response(200, json=_trip_payload())
        )
        respx.get(f"{_VOXTRAL_BASE}/health").mock(side_effect=httpx.ConnectError("nope"))

        result = runner.invoke(app, ["synthesize-trip", _URL, "--out", str(out_dir)])

        assert result.exit_code == 1
        assert "unreachable" in result.output.lower() or "error" in result.output.lower()

    @respx.mock
    def test_caches_audio_across_steps(self, runner: CliRunner, out_dir: Path) -> None:
        _, _, speech_route = _mock_happy_path()

        first = runner.invoke(app, ["synthesize-trip", _URL, "--out", str(out_dir)])
        second = runner.invoke(app, ["synthesize-trip", _URL, "--out", str(out_dir)])

        assert first.exit_code == 0
        assert second.exit_code == 0
        # Same chunks both runs → second run hits the audio cache.
        # First run: step 0 (intro+2 paragraphs=3) + step 2 (intro+1 paragraph=2) = 5 calls.
        assert speech_route.call_count == 5
