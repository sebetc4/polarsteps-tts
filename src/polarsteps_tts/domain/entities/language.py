from __future__ import annotations

from enum import StrEnum


class Language(StrEnum):
    """Supported synthesis languages. Value matches ISO 639-1 codes used by the TTS API."""

    FRENCH = "fr"
    ENGLISH = "en"
    SPANISH = "es"
    GERMAN = "de"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    DUTCH = "nl"
    ARABIC = "ar"
    HINDI = "hi"
