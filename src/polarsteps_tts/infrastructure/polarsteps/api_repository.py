from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from polarsteps_tts.domain.entities import Location, Step, Trip
from polarsteps_tts.domain.exceptions import (
    InfrastructureError,
    TripNotAccessible,
    TripNotFound,
)
from polarsteps_tts.domain.ports import TripRepository
from polarsteps_tts.domain.value_objects import TripId

API_BASE = "https://api.polarsteps.com"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Origin": "https://www.polarsteps.com",
    "Referer": "https://www.polarsteps.com/",
    "polarsteps-api-version": "62",
}


class PolarstepsApiRepository(TripRepository):
    """Reads public Polarsteps trips from the unofficial REST API."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        base_url: str = API_BASE,
        timeout: float = 30.0,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(headers=DEFAULT_HEADERS, timeout=timeout)
        self._base_url = base_url.rstrip("/")

    def get_by_id(self, trip_id: TripId, share_token: str | None = None) -> Trip:
        url = f"{self._base_url}/trips/{trip_id}"
        params = {"s": share_token} if share_token else None

        try:
            response = self._client.get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 404:
                raise TripNotFound(str(trip_id)) from e
            if status in (401, 403):
                raise TripNotAccessible(str(trip_id)) from e
            raise InfrastructureError(f"Polarsteps API returned HTTP {status}") from e
        except httpx.HTTPError as e:
            raise InfrastructureError(f"Polarsteps API request failed: {e}") from e

        return _trip_from_payload(response.json())

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> PolarstepsApiRepository:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _trip_from_payload(payload: dict[str, Any]) -> Trip:
    try:
        trip_id = TripId(str(payload["id"]))
        steps = tuple(_step_from_payload(s) for s in payload.get("all_steps", []))
        return Trip(
            id=trip_id,
            name=payload["name"],
            start_date=_to_datetime(payload["start_date"]),
            end_date=_to_datetime(payload["end_date"]),
            author_first_name=(payload.get("user") or {}).get("first_name"),
            steps=steps,
        )
    except (KeyError, TypeError, ValueError) as e:
        raise InfrastructureError(f"Unexpected Polarsteps payload shape: {e}") from e


def _step_from_payload(payload: dict[str, Any]) -> Step:
    raw_location = payload.get("location") or {}
    location = (
        Location(
            name=raw_location["name"],
            country_code=raw_location.get("country_code"),
            detail=raw_location.get("detail"),
            lat=raw_location.get("lat"),
            lon=raw_location.get("lon"),
        )
        if raw_location.get("name")
        else None
    )
    return Step(
        id=str(payload["id"]),
        name=payload.get("name") or "",
        start_time=_to_datetime(payload["start_time"]),
        description=payload.get("description"),
        location=location,
    )


def _to_datetime(timestamp: float | int) -> datetime:
    return datetime.fromtimestamp(float(timestamp), tz=UTC)
