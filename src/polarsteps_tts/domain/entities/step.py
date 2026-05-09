from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from polarsteps_tts.domain.entities.location import Location


@dataclass(frozen=True, slots=True)
class Step:
    id: str
    name: str
    start_time: datetime
    description: str | None = None
    location: Location | None = None

    @property
    def has_text(self) -> bool:
        return bool(self.description and self.description.strip())
