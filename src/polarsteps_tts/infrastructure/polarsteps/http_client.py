from __future__ import annotations

from typing import Any

import httpx

from polarsteps_tts.domain.exceptions import (
    InfrastructureError,
    TripNotAccessibleError,
    TripNotFoundError,
)
from polarsteps_tts.domain.value_objects import TripId

API_BASE = "https://api.polarsteps.com"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Origin": "https://www.polarsteps.com",
    "Referer": "https://www.polarsteps.com/",
    "polarsteps-api-version": "62",
}


class PolarstepsHttpClient:
    """Low-level HTTP client that fetches the raw Polarsteps trip payload.

    Only knows how to talk to the API and translate transport-level errors
    into domain exceptions. Does not parse the payload into entities.
    """

    def __init__(
        self,
        client: httpx.Client | None = None,
        base_url: str = API_BASE,
        timeout: float = 30.0,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(headers=DEFAULT_HEADERS, timeout=timeout)
        self._base_url = base_url.rstrip("/")

    def fetch_payload(self, trip_id: TripId, share_token: str | None = None) -> dict[str, Any]:
        url = f"{self._base_url}/trips/{trip_id}"
        params = {"s": share_token} if share_token else None

        try:
            response = self._client.get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 404:
                raise TripNotFoundError(str(trip_id)) from e
            if status in (401, 403):
                raise TripNotAccessibleError(str(trip_id)) from e
            raise InfrastructureError(f"Polarsteps API returned HTTP {status}") from e
        except httpx.HTTPError as e:
            raise InfrastructureError(f"Polarsteps API request failed: {e}") from e

        payload = response.json()
        if not isinstance(payload, dict):
            raise InfrastructureError("Polarsteps API returned a non-object payload")
        return payload

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> PolarstepsHttpClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
