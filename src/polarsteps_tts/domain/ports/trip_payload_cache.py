from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from polarsteps_tts.domain.value_objects import TripId


@dataclass(frozen=True, slots=True)
class CachedPayload:
    payload: dict[str, Any]
    fetched_at: datetime  # always UTC


class TripPayloadCache(Protocol):
    """Stores raw Polarsteps payloads keyed by trip id.

    The cache is dumb: it stores and retrieves bytes-equivalent data and
    knows nothing about freshness. Freshness is a domain concern handled
    by `FreshnessPolicy`.
    """

    def get(self, trip_id: TripId) -> CachedPayload | None: ...
    def put(self, trip_id: TripId, payload: dict[str, Any]) -> None: ...
    def invalidate(self, trip_id: TripId) -> None: ...
