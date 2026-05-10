from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain-level errors. Carries no technical details."""


class InvalidTripIdError(DomainError):
    def __init__(self, value: object) -> None:
        super().__init__(f"Invalid trip id: {value!r}")
        self.value = value


class InvalidTripUrlError(DomainError):
    def __init__(self, url: str) -> None:
        super().__init__(f"Invalid Polarsteps trip URL: {url!r}")
        self.url = url


class TripNotFoundError(DomainError):
    def __init__(self, trip_id: str) -> None:
        super().__init__(f"Trip not found: {trip_id}")
        self.trip_id = trip_id


class TripNotAccessibleError(DomainError):
    """Raised when a trip exists but cannot be read (private, missing share token)."""

    def __init__(self, trip_id: str) -> None:
        super().__init__(f"Trip is not publicly accessible: {trip_id}")
        self.trip_id = trip_id


class InfrastructureError(DomainError):
    """Generic wrapper for any unrecoverable infrastructure-level failure."""


class TtsEngineError(InfrastructureError):
    """Generic TTS engine failure (network, model unavailable, OOM)."""


class TtsEngineUnavailableError(TtsEngineError):
    """Raised when the TTS engine cannot serve requests (health check failed)."""


class TtsTextRejectedError(DomainError):
    """Raised when input text cannot be synthesized (empty, too long, unknown voice)."""


class EmptyStepTextError(DomainError):
    """Raised when a step has no narratable text (before or after cleaning)."""


__all__ = [
    "DomainError",
    "EmptyStepTextError",
    "InfrastructureError",
    "InvalidTripIdError",
    "InvalidTripUrlError",
    "TripNotAccessibleError",
    "TripNotFoundError",
    "TtsEngineError",
    "TtsEngineUnavailableError",
    "TtsTextRejectedError",
]
