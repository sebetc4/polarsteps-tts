from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from polarsteps_tts.presentation.cli import app

_BASE = "https://api.polarsteps.com"
_URL = "https://www.polarsteps.com/Alice/23964761-tour-mont-blanc"


def _payload() -> dict[str, object]:
    return {
        "id": 23964761,
        "name": "Tour du Mont-Blanc",
        "start_date": 1721000000,
        "end_date": 1721800000,
        "user": {"first_name": "Alice"},
        "all_steps": [
            {
                "id": 1,
                "name": "Refuge",
                "description": "Texte du post.",
                "start_time": 1721232000,
                "location": {"name": "Bourg-Saint-Maurice"},
            }
        ],
    }


@pytest.fixture
def runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    return CliRunner()


class TestFetchCommand:
    @respx.mock
    def test_fetch_prints_summary(self, runner: CliRunner) -> None:
        respx.get(f"{_BASE}/trips/23964761").mock(return_value=httpx.Response(200, json=_payload()))

        result = runner.invoke(app, ["fetch", _URL])

        assert result.exit_code == 0, result.output
        assert "Tour du Mont-Blanc" in result.output
        assert "Alice" in result.output

    @respx.mock
    def test_fetch_uses_cache_on_second_call(self, runner: CliRunner) -> None:
        route = respx.get(f"{_BASE}/trips/23964761").mock(
            return_value=httpx.Response(200, json=_payload())
        )

        first = runner.invoke(app, ["fetch", _URL])
        second = runner.invoke(app, ["fetch", _URL])

        assert first.exit_code == 0
        assert second.exit_code == 0
        assert route.call_count == 1  # second call served from cache

    @respx.mock
    def test_no_cache_bypasses_cache(self, runner: CliRunner) -> None:
        route = respx.get(f"{_BASE}/trips/23964761").mock(
            return_value=httpx.Response(200, json=_payload())
        )

        runner.invoke(app, ["fetch", _URL])
        runner.invoke(app, ["fetch", _URL, "--no-cache"])

        assert route.call_count == 2

    @respx.mock
    def test_refresh_forces_refetch(self, runner: CliRunner) -> None:
        route = respx.get(f"{_BASE}/trips/23964761").mock(
            return_value=httpx.Response(200, json=_payload())
        )

        runner.invoke(app, ["fetch", _URL])  # populate cache
        runner.invoke(app, ["fetch", _URL, "--refresh"])

        assert route.call_count == 2

    def test_invalid_url_exits_2(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["fetch", "https://example.com/foo"])
        assert result.exit_code == 2
        assert "Invalid URL" in result.output

    @respx.mock
    def test_404_exits_1(self, runner: CliRunner) -> None:
        respx.get(f"{_BASE}/trips/23964761").mock(return_value=httpx.Response(404))
        result = runner.invoke(app, ["fetch", _URL])
        assert result.exit_code == 1
        assert "Error" in result.output
