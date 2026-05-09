from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Location:
    name: str
    country_code: str | None = None
    detail: str | None = None
    lat: float | None = None
    lon: float | None = None

    def display_name(self) -> str:
        if self.detail:
            return f"{self.name}, {self.detail}"
        return self.name
