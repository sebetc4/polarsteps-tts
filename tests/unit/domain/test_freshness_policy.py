from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polarsteps_tts.domain.services import FreshnessPolicy

_NOW = datetime(2026, 5, 10, 12, 0, tzinfo=UTC)


class TestFreshnessPolicy:
    def test_finished_trip_within_finished_ttl_is_fresh(self) -> None:
        policy = FreshnessPolicy()
        assert policy.is_fresh(
            fetched_at=_NOW - timedelta(days=1),
            trip_end_date=_NOW - timedelta(days=10),
            now=_NOW,
        )

    def test_finished_trip_past_finished_ttl_is_stale(self) -> None:
        policy = FreshnessPolicy()
        assert not policy.is_fresh(
            fetched_at=_NOW - timedelta(days=31),
            trip_end_date=_NOW - timedelta(days=60),
            now=_NOW,
        )

    def test_ongoing_trip_within_ongoing_ttl_is_fresh(self) -> None:
        policy = FreshnessPolicy()
        assert policy.is_fresh(
            fetched_at=_NOW - timedelta(hours=5),
            trip_end_date=_NOW + timedelta(days=2),
            now=_NOW,
        )

    def test_ongoing_trip_past_ongoing_ttl_is_stale(self) -> None:
        policy = FreshnessPolicy()
        assert not policy.is_fresh(
            fetched_at=_NOW - timedelta(hours=7),
            trip_end_date=_NOW + timedelta(days=2),
            now=_NOW,
        )

    def test_zero_ttl_is_always_stale(self) -> None:
        policy = FreshnessPolicy(
            ongoing_ttl=timedelta(0),
            finished_ttl=timedelta(0),
        )
        assert not policy.is_fresh(
            fetched_at=_NOW,
            trip_end_date=_NOW - timedelta(days=1),
            now=_NOW,
        )

    def test_custom_ongoing_ttl_is_respected(self) -> None:
        policy = FreshnessPolicy(ongoing_ttl=timedelta(minutes=15))
        assert policy.is_fresh(
            fetched_at=_NOW - timedelta(minutes=10),
            trip_end_date=_NOW + timedelta(days=1),
            now=_NOW,
        )
        assert not policy.is_fresh(
            fetched_at=_NOW - timedelta(minutes=20),
            trip_end_date=_NOW + timedelta(days=1),
            now=_NOW,
        )

    def test_none_end_date_is_treated_as_ongoing(self) -> None:
        policy = FreshnessPolicy()
        # Within ongoing_ttl: fresh
        assert policy.is_fresh(
            fetched_at=_NOW - timedelta(hours=5),
            trip_end_date=None,
            now=_NOW,
        )
        # Past ongoing_ttl: stale
        assert not policy.is_fresh(
            fetched_at=_NOW - timedelta(hours=7),
            trip_end_date=None,
            now=_NOW,
        )

    def test_none_end_date_does_not_use_finished_ttl(self) -> None:
        # An ongoing trip 25 days old must NOT be considered fresh under the
        # 30-day finished_ttl — it should fall under the 6-hour ongoing_ttl.
        policy = FreshnessPolicy()
        assert not policy.is_fresh(
            fetched_at=_NOW - timedelta(days=25),
            trip_end_date=None,
            now=_NOW,
        )
