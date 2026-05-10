from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from polarsteps_tts.domain.entities import Trip

_DEFAULT_FRENCH_CHARS_PER_SECOND = 14.0


@dataclass(frozen=True, slots=True)
class EstimatedDuration:
    chars: int
    duration: timedelta

    @property
    def seconds(self) -> float:
        return self.duration.total_seconds()

    @property
    def minutes(self) -> float:
        return self.seconds / 60


@dataclass(frozen=True, slots=True)
class AudioEstimator:
    chars_per_second: float = _DEFAULT_FRENCH_CHARS_PER_SECOND

    def __post_init__(self) -> None:
        if self.chars_per_second <= 0:
            raise ValueError(f"chars_per_second must be positive, got {self.chars_per_second}")

    def estimate(self, trip: Trip) -> EstimatedDuration:
        chars = sum(len(s.description or "") for s in trip.steps_with_text)
        return EstimatedDuration(
            chars=chars,
            duration=timedelta(seconds=chars / self.chars_per_second),
        )
