from __future__ import annotations

from dataclasses import dataclass

from polarsteps_tts.domain.exceptions import InvalidTripId


@dataclass(frozen=True, slots=True)
class TripId:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.isdigit():
            raise InvalidTripId(self.value)

    def __str__(self) -> str:
        return self.value
