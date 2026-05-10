from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from polarsteps_tts.domain.entities import Location, Step, Trip
from polarsteps_tts.domain.exceptions import InfrastructureError
from polarsteps_tts.domain.value_objects import TripId

_logger = logging.getLogger(__name__)

_MILLISECOND_THRESHOLD = 1e11


def parse_trip_payload(payload: dict[str, Any]) -> Trip:
    """Translate a raw Polarsteps JSON payload into a Trip entity."""
    try:
        trip_id = TripId(str(payload["id"]))
        raw_steps = payload.get("all_steps") or []
        parsed = tuple(
            step for step in (_safe_step_from_payload(s) for s in raw_steps) if step is not None
        )
        steps = _sort_and_index_steps(parsed)
        return Trip(
            id=trip_id,
            name=payload.get("name") or f"Voyage {trip_id.value}",
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


def _safe_step_from_payload(payload: dict[str, Any]) -> Step | None:
    try:
        return _step_from_payload(payload)
    except (KeyError, TypeError, ValueError) as e:
        _logger.warning("skipping malformed step (id=%r): %s", payload.get("id"), e)
        return None


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
        position=0,
        description=payload.get("description"),
        location=location,
    )


def _sort_and_index_steps(steps: tuple[Step, ...]) -> tuple[Step, ...]:
    sorted_steps = sorted(steps, key=lambda s: (s.start_time, s.id))
    return tuple(replace(s, position=i + 1) for i, s in enumerate(sorted_steps))


def _to_datetime(timestamp: float | int) -> datetime:
    ts = float(timestamp)
    if ts > _MILLISECOND_THRESHOLD:
        ts /= 1000
    return datetime.fromtimestamp(ts, tz=UTC)
