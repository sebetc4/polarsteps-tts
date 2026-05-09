from __future__ import annotations

from datetime import UTC, datetime

from polarsteps_tts.domain.entities import Location, Step, Trip
from polarsteps_tts.domain.value_objects import TripId


def _make_step(step_id: str = "1", description: str | None = "Hello world") -> Step:
    return Step(
        id=step_id,
        name="Some step",
        start_time=datetime(2024, 7, 15, tzinfo=UTC),
        description=description,
        location=Location(name="Paris", country_code="FR"),
    )


class TestStep:
    def test_has_text_when_description_is_set(self) -> None:
        assert _make_step(description="content").has_text is True

    def test_has_text_false_when_description_is_none(self) -> None:
        assert _make_step(description=None).has_text is False

    def test_has_text_false_when_description_is_blank(self) -> None:
        assert _make_step(description="   ").has_text is False


class TestTrip:
    def test_steps_with_text_filters_empty_descriptions(self) -> None:
        trip = Trip(
            id=TripId("42"),
            name="Test",
            start_date=datetime(2024, 7, 15, tzinfo=UTC),
            end_date=datetime(2024, 7, 25, tzinfo=UTC),
            author_first_name="Alice",
            steps=(
                _make_step("1", "with text"),
                _make_step("2", None),
                _make_step("3", ""),
                _make_step("4", "more text"),
            ),
        )
        assert tuple(s.id for s in trip.steps_with_text) == ("1", "4")

    def test_total_text_length_counts_all_descriptions(self) -> None:
        trip = Trip(
            id=TripId("42"),
            name="Test",
            start_date=datetime(2024, 7, 15, tzinfo=UTC),
            end_date=datetime(2024, 7, 25, tzinfo=UTC),
            author_first_name=None,
            steps=(
                _make_step("1", "abc"),  # 3
                _make_step("2", None),  # 0
                _make_step("3", "hello"),  # 5
            ),
        )
        assert trip.total_text_length == 8


class TestLocation:
    def test_display_name_uses_detail_when_present(self) -> None:
        location = Location(name="Bourg-Saint-Maurice", detail="Savoie, France")
        assert location.display_name() == "Bourg-Saint-Maurice, Savoie, France"

    def test_display_name_falls_back_to_name(self) -> None:
        location = Location(name="Paris")
        assert location.display_name() == "Paris"
