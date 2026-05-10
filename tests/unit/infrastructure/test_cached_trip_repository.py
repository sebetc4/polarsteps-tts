from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from pytest_mock import MockerFixture

from polarsteps_tts.domain.ports import CachedPayload, TripPayloadCache
from polarsteps_tts.domain.services import FreshnessPolicy
from polarsteps_tts.domain.value_objects import TripId
from polarsteps_tts.infrastructure.polarsteps import (
    CachedTripRepository,
    PolarstepsHttpClient,
)

_NOW = datetime(2026, 5, 10, 12, 0, tzinfo=UTC)
_TRIP_ID = TripId("23964761")


def _payload(end_date: datetime, trip_name: str = "Tour du Mont-Blanc") -> dict[str, object]:
    return {
        "id": int(str(_TRIP_ID)),
        "name": trip_name,
        "start_date": (end_date - timedelta(days=10)).timestamp(),
        "end_date": end_date.timestamp(),
        "user": {"first_name": "Alice"},
        "all_steps": [],
    }


def _build(
    mocker: MockerFixture,
    cached: CachedPayload | None = None,
    fetched_payload: dict[str, object] | None = None,
    now: datetime = _NOW,
) -> tuple[CachedTripRepository, object, object]:
    http_client = mocker.Mock(spec=PolarstepsHttpClient)
    if fetched_payload is not None:
        http_client.fetch_payload.return_value = fetched_payload

    cache = mocker.Mock(spec=TripPayloadCache)
    cache.get.return_value = cached

    repo = CachedTripRepository(
        http_client=cast(PolarstepsHttpClient, http_client),
        cache=cast(TripPayloadCache, cache),
        freshness=FreshnessPolicy(),
        clock=lambda: now,
    )
    return repo, http_client, cache


class TestCachedTripRepository:
    def test_cache_miss_fetches_and_stores(self, mocker: MockerFixture) -> None:
        payload = _payload(end_date=_NOW + timedelta(days=2))
        repo, http_client, cache = _build(mocker, cached=None, fetched_payload=payload)

        trip = repo.get_by_id(_TRIP_ID)

        assert trip.id == _TRIP_ID
        http_client.fetch_payload.assert_called_once_with(_TRIP_ID, None)
        cache.put.assert_called_once_with(_TRIP_ID, payload)

    def test_cache_hit_fresh_skips_fetch(self, mocker: MockerFixture) -> None:
        payload = _payload(end_date=_NOW + timedelta(days=2))  # ongoing
        cached = CachedPayload(
            payload=payload,
            fetched_at=_NOW - timedelta(hours=1),  # well within ongoing TTL (6h)
        )
        repo, http_client, cache = _build(mocker, cached=cached)

        trip = repo.get_by_id(_TRIP_ID)

        assert trip.name == "Tour du Mont-Blanc"
        http_client.fetch_payload.assert_not_called()
        cache.put.assert_not_called()

    def test_cache_hit_stale_refetches(self, mocker: MockerFixture) -> None:
        old_payload = _payload(end_date=_NOW + timedelta(days=2), trip_name="OLD")
        new_payload = _payload(end_date=_NOW + timedelta(days=2), trip_name="NEW")
        cached = CachedPayload(
            payload=old_payload,
            fetched_at=_NOW - timedelta(hours=10),  # > 6h ongoing TTL
        )
        repo, http_client, cache = _build(mocker, cached=cached, fetched_payload=new_payload)

        trip = repo.get_by_id(_TRIP_ID)

        assert trip.name == "NEW"
        http_client.fetch_payload.assert_called_once()
        cache.put.assert_called_once_with(_TRIP_ID, new_payload)

    def test_finished_trip_uses_finished_ttl(self, mocker: MockerFixture) -> None:
        # Trip ended 5 days ago, cache 10 days old → still within 30d finished TTL
        payload = _payload(end_date=_NOW - timedelta(days=5))
        cached = CachedPayload(
            payload=payload,
            fetched_at=_NOW - timedelta(days=10),
        )
        repo, http_client, _cache = _build(mocker, cached=cached)

        repo.get_by_id(_TRIP_ID)

        http_client.fetch_payload.assert_not_called()

    def test_share_token_is_passed_to_fetcher(self, mocker: MockerFixture) -> None:
        payload = _payload(end_date=_NOW + timedelta(days=2))
        repo, http_client, _cache = _build(mocker, cached=None, fetched_payload=payload)

        repo.get_by_id(_TRIP_ID, share_token="abc-123")

        http_client.fetch_payload.assert_called_once_with(_TRIP_ID, "abc-123")

    def test_fetcher_error_on_cache_miss_propagates(self, mocker: MockerFixture) -> None:
        from polarsteps_tts.domain.exceptions import TripNotFoundError

        repo, http_client, cache = _build(mocker, cached=None)
        http_client.fetch_payload.side_effect = TripNotFoundError(str(_TRIP_ID))

        with pytest.raises(TripNotFoundError):
            repo.get_by_id(_TRIP_ID)

        cache.put.assert_not_called()
