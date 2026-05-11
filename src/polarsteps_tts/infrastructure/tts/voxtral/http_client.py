from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from polarsteps_tts.domain.exceptions import (
    TtsEngineError,
    TtsTextRejectedError,
)

_logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8091"
DEFAULT_MODEL = "mistralai/Voxtral-4B-TTS-2603"

# First call after server start is slower (potential lazy-warmup paths even after
# CUDA graphs are captured). Subsequent calls are fast.
DEFAULT_TIMEOUT_FIRST_CALL = 120.0
DEFAULT_TIMEOUT_STEADY_STATE = 60.0
DEFAULT_HEALTH_TIMEOUT = 5.0

# Retry on transient transport errors only — never on 4xx (text/voice rejected).
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1.0


class VoxtralHttpClient:
    """Thin HTTP wrapper over Voxtral's `/v1/audio/speech` endpoint.

    Translates transport-level errors into domain exceptions:
    - HTTP 4xx        -> `TtsTextRejectedError` (input is the problem)
    - HTTP 5xx        -> `TtsEngineError` (after retries)
    - Connect/timeout -> `TtsEngineError` (after retries)
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        client: httpx.Client | None = None,
        timeout_first_call: float = DEFAULT_TIMEOUT_FIRST_CALL,
        timeout_steady_state: float = DEFAULT_TIMEOUT_STEADY_STATE,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._owns_client = client is None
        self._timeout_first_call = timeout_first_call
        self._timeout_steady_state = timeout_steady_state
        self._warmed_up = False
        self._client = client or httpx.Client()

    @property
    def base_url(self) -> str:
        return self._base_url

    def post_speech(
        self,
        text: str,
        voice: str,
        language: str = "fr",
        speed: float = 1.0,
        instructions: str | None = None,
        seed: int | None = None,
    ) -> bytes:
        """Return raw WAV bytes from Voxtral. Raises domain exceptions on failure."""
        payload: dict[str, Any] = {
            "input": text,
            "model": self._model,
            "voice": voice,
            "response_format": "wav",
            "language": language,
            "speed": speed,
        }
        if instructions is not None:
            payload["instructions"] = instructions
        if seed is not None:
            payload["seed"] = seed

        return self._post_with_retry(payload)

    def is_alive(self) -> bool:
        """Probe `GET /health`. Returns True iff the server replies 200 within timeout.

        Never raises — health checks should be cheap diagnostics, not throws.
        """
        try:
            response = self._client.get(f"{self._base_url}/health", timeout=DEFAULT_HEALTH_TIMEOUT)
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> VoxtralHttpClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _post_with_retry(self, payload: dict[str, Any]) -> bytes:
        url = f"{self._base_url}/v1/audio/speech"
        timeout = self._timeout_first_call if not self._warmed_up else self._timeout_steady_state
        last_transport_error: httpx.HTTPError | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client.post(url, json=payload, timeout=timeout)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
                last_transport_error = e
                _logger.warning(
                    "Voxtral transport error (attempt %d/%d): %s",
                    attempt + 1,
                    _MAX_RETRIES,
                    e,
                )
                self._sleep_for_retry(attempt)
                continue

            if 200 <= response.status_code < 300:
                self._warmed_up = True
                return response.content

            # 4xx: input/voice rejected, no retry
            if 400 <= response.status_code < 500:
                raise TtsTextRejectedError(
                    f"Voxtral rejected request (HTTP {response.status_code}): "
                    f"{_safe_body_excerpt(response)}"
                )

            # 5xx: server-side issue, retry
            if attempt < _MAX_RETRIES - 1:
                _logger.warning(
                    "Voxtral 5xx (attempt %d/%d): HTTP %d",
                    attempt + 1,
                    _MAX_RETRIES,
                    response.status_code,
                )
                self._sleep_for_retry(attempt)
                continue
            raise TtsEngineError(
                f"Voxtral server error after {_MAX_RETRIES} attempts "
                f"(HTTP {response.status_code}): {_safe_body_excerpt(response)}"
            )

        raise TtsEngineError(
            f"Voxtral unreachable after {_MAX_RETRIES} attempts: {last_transport_error}"
        )

    @staticmethod
    def _sleep_for_retry(attempt: int) -> None:
        time.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))


def _safe_body_excerpt(response: httpx.Response, max_chars: int = 200) -> str:
    try:
        body = response.text
    except (UnicodeDecodeError, httpx.HTTPError):
        return "<binary body>"
    return body[:max_chars]
