from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from polarsteps_tts.domain.exceptions import InfrastructureError
from polarsteps_tts.infrastructure.polarsteps.payload_parser import (
    parse_end_date,
    parse_trip_payload,
)


def _payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": 23964761,
        "name": "Tour du Mont-Blanc",
        "start_date": 1721000000,
        "end_date": 1721800000,
        "user": {"first_name": "Alice"},
        "all_steps": [
            {
                "id": 12345,
                "name": "Refuge des Mottets",
                "description": "Réveil aux aurores...",
                "start_time": 1721232000,
                "location": {
                    "name": "Bourg-Saint-Maurice",
                    "country_code": "FR",
                    "detail": "Savoie, France",
                    "lat": 45.62,
                    "lon": 6.77,
                },
            },
            {
                "id": 12346,
                "name": "Tracking-only step",
                "description": None,
                "start_time": 1721240000,
                "location": None,
            },
        ],
    }
    base.update(overrides)
    return base


class TestHappyPath:
    def test_returns_trip_with_expected_fields(self) -> None:
        trip = parse_trip_payload(_payload())

        assert trip.id.value == "23964761"
        assert trip.name == "Tour du Mont-Blanc"
        assert trip.author_first_name == "Alice"
        assert trip.start_date == datetime(2024, 7, 14, 23, 33, 20, tzinfo=UTC)
        assert trip.end_date == datetime(2024, 7, 24, 5, 46, 40, tzinfo=UTC)
        assert len(trip.steps) == 2

    def test_parses_step_with_full_location(self) -> None:
        trip = parse_trip_payload(_payload())
        step = trip.steps[0]

        assert step.id == "12345"
        assert step.name == "Refuge des Mottets"
        assert step.description == "Réveil aux aurores..."
        assert step.location is not None
        assert step.location.name == "Bourg-Saint-Maurice"
        assert step.location.country_code == "FR"
        assert step.location.detail == "Savoie, France"
        assert step.location.lat == 45.62
        assert step.location.lon == 6.77

    def test_step_without_location_yields_none(self) -> None:
        trip = parse_trip_payload(_payload())
        assert trip.steps[1].location is None

    def test_step_without_description_yields_none(self) -> None:
        trip = parse_trip_payload(_payload())
        assert trip.steps[1].description is None
        assert trip.steps[1].has_text is False

    def test_handles_null_user(self) -> None:
        trip = parse_trip_payload(_payload(user=None))
        assert trip.author_first_name is None

    def test_handles_missing_user_first_name(self) -> None:
        trip = parse_trip_payload(_payload(user={}))
        assert trip.author_first_name is None

    def test_handles_empty_all_steps(self) -> None:
        trip = parse_trip_payload(_payload(all_steps=[]))
        assert trip.steps == ()

    def test_handles_missing_all_steps(self) -> None:
        payload = _payload()
        del payload["all_steps"]
        trip = parse_trip_payload(payload)
        assert trip.steps == ()


class TestErrors:
    def test_missing_id_raises_infrastructure_error(self) -> None:
        payload = _payload()
        del payload["id"]
        with pytest.raises(InfrastructureError):
            parse_trip_payload(payload)

    def test_missing_start_date_raises_infrastructure_error(self) -> None:
        payload = _payload()
        del payload["start_date"]
        with pytest.raises(InfrastructureError):
            parse_trip_payload(payload)

    def test_missing_end_date_raises_infrastructure_error(self) -> None:
        payload = _payload()
        del payload["end_date"]
        with pytest.raises(InfrastructureError):
            parse_trip_payload(payload)

    def test_invalid_timestamp_type_raises_infrastructure_error(self) -> None:
        with pytest.raises(InfrastructureError):
            parse_trip_payload(_payload(start_date="not-a-number"))


class TestRobustness:
    def test_falls_back_on_missing_trip_name(self, caplog: pytest.LogCaptureFixture) -> None:
        payload = _payload()
        del payload["name"]
        trip = parse_trip_payload(payload)
        assert trip.name == "Voyage 23964761"

    def test_falls_back_on_null_trip_name(self) -> None:
        trip = parse_trip_payload(_payload(name=None))
        assert trip.name == "Voyage 23964761"

    def test_skips_step_without_start_time(self, caplog: pytest.LogCaptureFixture) -> None:
        payload = _payload(
            all_steps=[
                {
                    "id": 1,
                    "name": "Good step",
                    "description": "ok",
                    "start_time": 1721232000,
                    "location": None,
                },
                {
                    "id": 2,
                    "name": "Broken step",
                    "description": "no start_time here",
                    "location": None,
                },
            ]
        )
        with caplog.at_level("WARNING"):
            trip = parse_trip_payload(payload)

        assert len(trip.steps) == 1
        assert trip.steps[0].id == "1"
        assert any("skipping malformed step" in rec.message for rec in caplog.records)

    def test_skips_step_without_id(self) -> None:
        payload = _payload(
            all_steps=[
                {
                    "name": "Orphan",
                    "description": "no id",
                    "start_time": 1721232000,
                    "location": None,
                },
            ]
        )
        trip = parse_trip_payload(payload)
        assert trip.steps == ()

    def test_keeps_other_steps_when_one_is_broken(self) -> None:
        payload = _payload(
            all_steps=[
                {
                    "id": 1,
                    "name": "Ok",
                    "description": "fine",
                    "start_time": 1721232000,
                    "location": None,
                },
                {"id": 2, "name": "broken"},
                {
                    "id": 3,
                    "name": "Also ok",
                    "description": "fine too",
                    "start_time": 1721240000,
                    "location": None,
                },
            ]
        )
        trip = parse_trip_payload(payload)
        assert tuple(s.id for s in trip.steps) == ("1", "3")

    def test_handles_millisecond_timestamps(self) -> None:
        payload = _payload(
            start_date=1721000000000,
            end_date=1721800000000,
            all_steps=[
                {
                    "id": 1,
                    "name": "Step in ms",
                    "description": "x",
                    "start_time": 1721232000000,
                    "location": None,
                }
            ],
        )
        trip = parse_trip_payload(payload)
        assert trip.start_date == datetime(2024, 7, 14, 23, 33, 20, tzinfo=UTC)
        assert trip.steps[0].start_time == datetime(2024, 7, 17, 16, 0, tzinfo=UTC)

    def test_step_name_falls_back_to_empty_string(self) -> None:
        payload = _payload(
            all_steps=[
                {
                    "id": 1,
                    "description": "no name",
                    "start_time": 1721232000,
                    "location": None,
                }
            ]
        )
        trip = parse_trip_payload(payload)
        assert trip.steps[0].name == ""


class TestSortAndPosition:
    def test_sorts_steps_by_start_time(self) -> None:
        payload = _payload(
            all_steps=[
                {
                    "id": 30,
                    "name": "third",
                    "description": "x",
                    "start_time": 1721240000,
                    "location": None,
                },
                {
                    "id": 10,
                    "name": "first",
                    "description": "x",
                    "start_time": 1721220000,
                    "location": None,
                },
                {
                    "id": 20,
                    "name": "second",
                    "description": "x",
                    "start_time": 1721230000,
                    "location": None,
                },
            ]
        )
        trip = parse_trip_payload(payload)
        assert tuple(s.id for s in trip.steps) == ("10", "20", "30")

    def test_assigns_1_based_position(self) -> None:
        trip = parse_trip_payload(_payload())
        positions = tuple(s.position for s in trip.steps)
        assert positions == (1, 2)

    def test_position_matches_sorted_order_not_payload_order(self) -> None:
        payload = _payload(
            all_steps=[
                {
                    "id": 99,
                    "name": "later",
                    "description": "x",
                    "start_time": 1721240000,
                    "location": None,
                },
                {
                    "id": 1,
                    "name": "earlier",
                    "description": "x",
                    "start_time": 1721220000,
                    "location": None,
                },
            ]
        )
        trip = parse_trip_payload(payload)
        by_id = {s.id: s.position for s in trip.steps}
        assert by_id == {"1": 1, "99": 2}

    def test_breaks_ties_by_id(self) -> None:
        payload = _payload(
            all_steps=[
                {
                    "id": 22,
                    "name": "b",
                    "description": "x",
                    "start_time": 1721232000,
                    "location": None,
                },
                {
                    "id": 11,
                    "name": "a",
                    "description": "x",
                    "start_time": 1721232000,
                    "location": None,
                },
            ]
        )
        trip = parse_trip_payload(payload)
        assert tuple(s.id for s in trip.steps) == ("11", "22")
        assert tuple(s.position for s in trip.steps) == (1, 2)

    def test_position_stable_across_text_filtering(self) -> None:
        payload = _payload(
            all_steps=[
                {
                    "id": 1,
                    "name": "with text",
                    "description": "narrate me",
                    "start_time": 1721220000,
                    "location": None,
                },
                {
                    "id": 2,
                    "name": "silent",
                    "description": None,
                    "start_time": 1721230000,
                    "location": None,
                },
                {
                    "id": 3,
                    "name": "with text again",
                    "description": "narrate me too",
                    "start_time": 1721240000,
                    "location": None,
                },
            ]
        )
        trip = parse_trip_payload(payload)
        assert tuple(s.position for s in trip.steps) == (1, 2, 3)
        assert tuple(s.position for s in trip.steps_with_text) == (1, 3)

    def test_empty_payload_yields_empty_steps(self) -> None:
        trip = parse_trip_payload(_payload(all_steps=[]))
        assert trip.steps == ()


class TestParseEndDate:
    def test_returns_utc_datetime(self) -> None:
        end = parse_end_date(_payload())
        assert end == datetime(2024, 7, 24, 5, 46, 40, tzinfo=UTC)

    def test_missing_raises_infrastructure_error(self) -> None:
        payload = _payload()
        del payload["end_date"]
        with pytest.raises(InfrastructureError):
            parse_end_date(payload)
