from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_VALID_SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_FALLBACK = "untitled"


@dataclass(frozen=True, slots=True)
class Slug:
    value: str

    def __post_init__(self) -> None:
        if not _VALID_SLUG_RE.fullmatch(self.value):
            raise ValueError(f"Invalid slug: {self.value!r}")

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_text(cls, text: str, max_length: int = 80) -> Slug:
        if max_length <= 0:
            raise ValueError(f"max_length must be positive, got {max_length}")

        ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        cleaned = _NON_ALNUM_RE.sub("-", ascii_text.lower()).strip("-")
        if not cleaned:
            return cls(_FALLBACK)
        return cls(_truncate_at_word_boundary(cleaned, max_length))


def _truncate_at_word_boundary(slug: str, max_length: int) -> str:
    if len(slug) <= max_length:
        return slug
    if slug[max_length] == "-":
        return slug[:max_length]
    truncated = slug[:max_length]
    last_dash = truncated.rfind("-")
    if last_dash > 0:
        return truncated[:last_dash]
    return truncated
