from __future__ import annotations

import re

from polarsteps_tts.domain.exceptions import InvalidTripUrlError
from polarsteps_tts.domain.value_objects import TripId

_TRIP_URL_PATTERN = re.compile(
    r"polarsteps\.com/[^/]+/(?P<trip_id>\d+)-[^?]+(?:\?s=(?P<share_token>[\w\-]+))?"
)


def parse_trip_url(url: str) -> tuple[TripId, str | None]:
    """Extract the trip id and optional share token from a Polarsteps URL.

    Raises:
        InvalidTripUrlError: if the URL does not match the expected pattern.
    """
    match = _TRIP_URL_PATTERN.search(url)
    if match is None:
        raise InvalidTripUrlError(url)
    return TripId(match.group("trip_id")), match.group("share_token")
