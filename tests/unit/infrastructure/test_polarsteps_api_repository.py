from __future__ import annotations

import httpx
import pytest
import respx

from polarsteps_tts.domain.exceptions import (
    InfrastructureError,
    TripNotAccessibleError,
    TripNotFoundError,
)
from polarsteps_tts.domain.value_objects import TripId
from polarsteps_tts.infrastructure.polarsteps import PolarstepsApiRepository

_BASE = "https://api.polarsteps.com"


def _payload() -> dict[str, object]:
    return {
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


class TestPolarstepsApiRepository:
    @respx.mock
    def test_returns_trip_on_200(self) -> None:
        respx.get(f"{_BASE}/trips/23964761").mock(return_value=httpx.Response(200, json=_payload()))
        with PolarstepsApiRepository() as repo:
            trip = repo.get_by_id(TripId("23964761"))

        assert trip.id == TripId("23964761")
        assert trip.name == "Tour du Mont-Blanc"
        assert trip.author_first_name == "Alice"
        assert len(trip.steps) == 2
        assert trip.steps[0].description == "Réveil aux aurores..."
        assert trip.steps[0].location is not None
        assert trip.steps[0].location.name == "Bourg-Saint-Maurice"
        assert trip.steps[1].location is None
        assert trip.steps[1].has_text is False

    @respx.mock
    def test_passes_share_token_as_query_param(self) -> None:
        route = respx.get(f"{_BASE}/trips/23964761", params={"s": "tok"}).mock(
            return_value=httpx.Response(200, json=_payload())
        )
        with PolarstepsApiRepository() as repo:
            repo.get_by_id(TripId("23964761"), share_token="tok")
        assert route.called

    @respx.mock
    def test_404_raises_trip_not_found(self) -> None:
        respx.get(f"{_BASE}/trips/42").mock(return_value=httpx.Response(404))
        with PolarstepsApiRepository() as repo, pytest.raises(TripNotFoundError):
            repo.get_by_id(TripId("42"))

    @respx.mock
    def test_401_raises_trip_not_accessible(self) -> None:
        respx.get(f"{_BASE}/trips/42").mock(return_value=httpx.Response(401))
        with PolarstepsApiRepository() as repo, pytest.raises(TripNotAccessibleError):
            repo.get_by_id(TripId("42"))

    @respx.mock
    def test_500_raises_infrastructure_error(self) -> None:
        respx.get(f"{_BASE}/trips/42").mock(return_value=httpx.Response(500))
        with PolarstepsApiRepository() as repo, pytest.raises(InfrastructureError):
            repo.get_by_id(TripId("42"))

    @respx.mock
    def test_malformed_payload_raises_infrastructure_error(self) -> None:
        respx.get(f"{_BASE}/trips/42").mock(
            return_value=httpx.Response(200, json={"id": 42})  # missing fields
        )
        with PolarstepsApiRepository() as repo, pytest.raises(InfrastructureError):
            repo.get_by_id(TripId("42"))
