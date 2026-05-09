from __future__ import annotations

import pytest

from polarsteps_tts.domain.exceptions import InvalidTripId
from polarsteps_tts.domain.value_objects import TripId


class TestTripId:
    def test_accepts_numeric_string(self) -> None:
        trip_id = TripId("23964761")
        assert str(trip_id) == "23964761"

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(InvalidTripId):
            TripId("")

    def test_rejects_non_numeric_string(self) -> None:
        with pytest.raises(InvalidTripId):
            TripId("abc")

    def test_is_immutable(self) -> None:
        trip_id = TripId("123")
        with pytest.raises((AttributeError, TypeError)):
            trip_id.value = "456"  # type: ignore[misc]

    def test_equality_by_value(self) -> None:
        assert TripId("123") == TripId("123")
        assert TripId("123") != TripId("456")
