from __future__ import annotations

from polarsteps_tts.domain.entities import Trip
from polarsteps_tts.domain.ports import TripRepository
from polarsteps_tts.domain.value_objects import TripId
from polarsteps_tts.infrastructure.polarsteps.http_client import PolarstepsHttpClient
from polarsteps_tts.infrastructure.polarsteps.payload_parser import parse_trip_payload


class PolarstepsApiRepository(TripRepository):
    """Reads public Polarsteps trips by composing an HTTP client and a payload parser."""

    def __init__(self, http_client: PolarstepsHttpClient | None = None) -> None:
        self._owns_client = http_client is None
        self._http_client = http_client or PolarstepsHttpClient()

    def get_by_id(self, trip_id: TripId, share_token: str | None = None) -> Trip:
        payload = self._http_client.fetch_payload(trip_id, share_token)
        return parse_trip_payload(payload)

    def close(self) -> None:
        if self._owns_client:
            self._http_client.close()

    def __enter__(self) -> PolarstepsApiRepository:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
