from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class FreshnessPolicy:
    """Decides whether a cached payload is still fresh enough to serve.

    A trip that has already ended is treated as stable, so a long TTL is
    acceptable. A trip still in progress is refetched more aggressively
    because the author may add new steps at any time.
    """

    ongoing_ttl: timedelta = timedelta(hours=6)
    finished_ttl: timedelta = timedelta(days=30)

    def is_fresh(
        self,
        fetched_at: datetime,
        trip_end_date: datetime | None,
        now: datetime,
    ) -> bool:
        is_ongoing = trip_end_date is None or trip_end_date >= now
        ttl = self.ongoing_ttl if is_ongoing else self.finished_ttl
        return (now - fetched_at) < ttl
