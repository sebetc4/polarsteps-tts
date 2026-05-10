from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polarsteps_tts.domain.entities import Step, Trip
from polarsteps_tts.domain.services import AudioEstimator
from polarsteps_tts.domain.value_objects import TripId


def _step(step_id: str, description: str | None, position: int) -> Step:
    return Step(
        id=step_id,
        name="step",
        start_time=datetime(2024, 7, 15, tzinfo=UTC),
        position=position,
        description=description,
    )


def _trip(*descriptions: str | None) -> Trip:
    return Trip(
        id=TripId("1"),
        name="Test",
        start_date=datetime(2024, 7, 15, tzinfo=UTC),
        end_date=datetime(2024, 7, 25, tzinfo=UTC),
        author_first_name=None,
        steps=tuple(_step(str(i + 1), d, i + 1) for i, d in enumerate(descriptions)),
    )


class TestAudioEstimator:
    def test_estimate_french_default_rate(self) -> None:
        trip = _trip("a" * 14000)
        result = AudioEstimator().estimate(trip)
        assert result.chars == 14000
        assert result.seconds == pytest.approx(1000.0)
        assert result.minutes == pytest.approx(16.666, abs=0.01)

    def test_estimate_ignores_steps_without_text(self) -> None:
        trip = _trip("hello", None, "world", "   ")
        result = AudioEstimator().estimate(trip)
        assert result.chars == 10  # "hello" + "world"

    def test_estimate_empty_trip(self) -> None:
        trip = _trip()
        result = AudioEstimator().estimate(trip)
        assert result.chars == 0
        assert result.seconds == 0.0

    def test_custom_rate(self) -> None:
        trip = _trip("a" * 100)
        result = AudioEstimator(chars_per_second=10.0).estimate(trip)
        assert result.seconds == pytest.approx(10.0)

    def test_zero_rate_rejected(self) -> None:
        with pytest.raises(ValueError, match="chars_per_second"):
            AudioEstimator(chars_per_second=0)

    def test_negative_rate_rejected(self) -> None:
        with pytest.raises(ValueError, match="chars_per_second"):
            AudioEstimator(chars_per_second=-5)
