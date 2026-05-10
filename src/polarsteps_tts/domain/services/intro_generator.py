from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from polarsteps_tts.domain.entities.narration_script import IntroSegment
from polarsteps_tts.domain.entities.step import Step

_FRENCH_MONTHS: dict[int, str] = {
    1: "janvier",
    2: "février",
    3: "mars",
    4: "avril",
    5: "mai",
    6: "juin",
    7: "juillet",
    8: "août",
    9: "septembre",
    10: "octobre",
    11: "novembre",
    12: "décembre",
}


@dataclass(frozen=True, slots=True)
class IntroGenerator:
    """Generate a spoken intro from a step's metadata.

    Pure service: no I/O, deterministic output. Date formatting uses an
    in-house French month table to avoid relying on system locales (Babel
    not pulled in as a dependency for a 12-entry table).
    """

    def generate(self, step: Step) -> IntroSegment:
        parts: list[str] = [self._title_clause(step)]
        parts.append(self._when_where_clause(step))
        return IntroSegment(text=" ".join(parts))

    @staticmethod
    def _title_clause(step: Step) -> str:
        title = step.name.strip() if step.name else ""
        if title:
            return f"Étape {step.position} : {title}."
        return f"Étape {step.position}."

    @staticmethod
    def _when_where_clause(step: Step) -> str:
        date_str = _format_french_date(step.start_time)
        location_str = step.location.display_name() if step.location else None
        if location_str:
            return f"Le {date_str}, à {location_str}."
        return f"Le {date_str}."


def _format_french_date(dt: datetime) -> str:
    """Format a datetime as 'DD mois YYYY' in French.

    Drops the leading zero on the day (1, 2, ..., 31). The first day of the
    month uses the ordinal '1er' as is customary in French.
    """
    day = dt.day
    day_str = "1er" if day == 1 else str(day)
    return f"{day_str} {_FRENCH_MONTHS[dt.month]} {dt.year}"
