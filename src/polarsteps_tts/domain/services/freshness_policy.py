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
        trip_end_date: datetime,
        now: datetime,
    ) -> bool:
        ttl = self.finished_ttl if trip_end_date < now else self.ongoing_ttl
        return (now - fetched_at) < ttl
