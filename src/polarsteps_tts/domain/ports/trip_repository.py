from __future__ import annotations

from typing import Protocol

from polarsteps_tts.domain.entities import Trip
from polarsteps_tts.domain.value_objects import TripId


class TripRepository(Protocol):
    """Port for retrieving a Trip from an external source.

    Implementations must translate any technical failure (HTTP, parsing, etc.)
    into a `DomainError` subclass before returning.
    """

    def get_by_id(self, trip_id: TripId, share_token: str | None = None) -> Trip: ...
