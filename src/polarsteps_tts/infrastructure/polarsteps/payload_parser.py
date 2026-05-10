from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from polarsteps_tts.domain.entities import Location, Step, Trip
from polarsteps_tts.domain.exceptions import InfrastructureError
from polarsteps_tts.domain.value_objects import TripId


def parse_trip_payload(payload: dict[str, Any]) -> Trip:
    """Translate a raw Polarsteps JSON payload into a Trip entity."""
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


def parse_end_date(payload: dict[str, Any]) -> datetime:
    """Extract the trip end_date from a raw payload, in UTC."""
    try:
        return _to_datetime(payload["end_date"])
    except (KeyError, TypeError, ValueError) as e:
        raise InfrastructureError(f"Missing or invalid end_date in payload: {e}") from e


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
