from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain-level errors. Carries no technical details."""


class InvalidTripId(DomainError):
    def __init__(self, value: object) -> None:
        super().__init__(f"Invalid trip id: {value!r}")
        self.value = value


class InvalidTripUrl(DomainError):
    def __init__(self, url: str) -> None:
        super().__init__(f"Invalid Polarsteps trip URL: {url!r}")
        self.url = url


class TripNotFound(DomainError):
    def __init__(self, trip_id: str) -> None:
        super().__init__(f"Trip not found: {trip_id}")
        self.trip_id = trip_id


class TripNotAccessible(DomainError):
    """Raised when a trip exists but cannot be read (private, missing share token)."""

    def __init__(self, trip_id: str) -> None:
        super().__init__(f"Trip is not publicly accessible: {trip_id}")
        self.trip_id = trip_id


class InfrastructureError(DomainError):
    """Generic wrapper for any unrecoverable infrastructure-level failure."""


__all__ = [
    "DomainError",
    "InfrastructureError",
    "InvalidTripId",
    "InvalidTripUrl",
    "TripNotAccessible",
    "TripNotFound",
]
