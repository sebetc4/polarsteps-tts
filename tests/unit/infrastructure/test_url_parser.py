from __future__ import annotations

import pytest

from polarsteps_tts.domain.exceptions import InvalidTripUrl
from polarsteps_tts.domain.value_objects import TripId
from polarsteps_tts.infrastructure.polarsteps import parse_trip_url


class TestParseTripUrl:
    def test_parses_public_trip_url(self) -> None:
        trip_id, share_token = parse_trip_url(
            "https://www.polarsteps.com/Alice/23964761-tour-mont-blanc"
        )
        assert trip_id == TripId("23964761")
        assert share_token is None

    def test_parses_shared_trip_url_with_token(self) -> None:
        trip_id, share_token = parse_trip_url(
            "https://www.polarsteps.com/Alice/23964761-tour-mont-blanc?s=abc-123"
        )
        assert trip_id == TripId("23964761")
        assert share_token == "abc-123"

    def test_rejects_unrelated_url(self) -> None:
        with pytest.raises(InvalidTripUrl):
            parse_trip_url("https://example.com/foo/bar")

    def test_rejects_url_without_trip_id(self) -> None:
        with pytest.raises(InvalidTripUrl):
            parse_trip_url("https://www.polarsteps.com/Alice/")
