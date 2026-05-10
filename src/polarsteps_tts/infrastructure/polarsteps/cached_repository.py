from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from polarsteps_tts.domain.entities import Trip
from polarsteps_tts.domain.ports import TripPayloadCache, TripRepository
from polarsteps_tts.domain.services import FreshnessPolicy
from polarsteps_tts.domain.value_objects import TripId
from polarsteps_tts.infrastructure.polarsteps.http_client import PolarstepsHttpClient
from polarsteps_tts.infrastructure.polarsteps.payload_parser import (
    parse_end_date,
    parse_trip_payload,
)

_logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class CachedTripRepository(TripRepository):
    """Trip repository that consults a cache before hitting the network.

    Composition:
        - `http_client` performs the actual fetch on cache miss / stale
        - `cache` stores the raw payload
        - `freshness` decides whether a cached payload is fresh enough
        - `clock` is injectable for deterministic tests
    """

    def __init__(
        self,
        http_client: PolarstepsHttpClient,
        cache: TripPayloadCache,
        freshness: FreshnessPolicy,
        clock: Clock = _utc_now,
    ) -> None:
        self._http_client = http_client
        self._cache = cache
        self._freshness = freshness
        self._clock = clock

    def get_by_id(self, trip_id: TripId, share_token: str | None = None) -> Trip:
        cached_trip = self._try_serve_from_cache(trip_id)
        if cached_trip is not None:
            return cached_trip

        payload = self._http_client.fetch_payload(trip_id, share_token)
        self._cache.put(trip_id, payload)
        return parse_trip_payload(payload)

    def _try_serve_from_cache(self, trip_id: TripId) -> Trip | None:
        cached = self._cache.get(trip_id)
        if cached is None:
            _logger.info("cache miss trip_id=%s", trip_id)
            return None

        end_date = parse_end_date(cached.payload)
        if not self._freshness.is_fresh(
            fetched_at=cached.fetched_at,
            trip_end_date=end_date,
            now=self._clock(),
        ):
            _logger.info("cache stale trip_id=%s, refetching", trip_id)
            return None

        _logger.info("cache hit trip_id=%s", trip_id)
        return parse_trip_payload(cached.payload)
