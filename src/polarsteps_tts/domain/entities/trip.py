from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from polarsteps_tts.domain.entities.step import Step
from polarsteps_tts.domain.value_objects import TripId


@dataclass(frozen=True, slots=True)
class Trip:
    id: TripId
    name: str
    start_date: datetime
    end_date: datetime
    author_first_name: str | None
    steps: tuple[Step, ...]

    @property
    def steps_with_text(self) -> tuple[Step, ...]:
        return tuple(s for s in self.steps if s.has_text)

    @property
    def total_text_length(self) -> int:
        return sum(len(s.description or "") for s in self.steps)
