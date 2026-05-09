from __future__ import annotations

from dataclasses import dataclass

from polarsteps_tts.domain.entities import Trip
from polarsteps_tts.domain.ports import TripRepository
from polarsteps_tts.domain.value_objects import TripId


@dataclass(frozen=True, slots=True)
class FetchTripCommand:
    trip_id: TripId
    share_token: str | None = None


class FetchTripUseCase:
    def __init__(self, repository: TripRepository) -> None:
        self._repository = repository

    def execute(self, command: FetchTripCommand) -> Trip:
        return self._repository.get_by_id(command.trip_id, command.share_token)
