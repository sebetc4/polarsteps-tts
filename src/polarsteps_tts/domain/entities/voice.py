from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias


class PresetVoice(StrEnum):
    """Voice presets exposed by Voxtral. Value = identifier sent to the API.

    Validated against `GET /v1/audio/voices` on the local Voxtral server.
    """

    # French (project priority)
    FR_FEMALE = "fr_female"
    FR_MALE = "fr_male"
    # Neutral / multilingual
    NEUTRAL_FEMALE = "neutral_female"
    NEUTRAL_MALE = "neutral_male"
    CASUAL_FEMALE = "casual_female"
    CASUAL_MALE = "casual_male"
    CHEERFUL_FEMALE = "cheerful_female"
    # Other languages
    DE_FEMALE = "de_female"
    DE_MALE = "de_male"
    ES_FEMALE = "es_female"
    ES_MALE = "es_male"
    IT_FEMALE = "it_female"
    IT_MALE = "it_male"
    NL_FEMALE = "nl_female"
    NL_MALE = "nl_male"
    PT_FEMALE = "pt_female"
    PT_MALE = "pt_male"
    AR_MALE = "ar_male"
    HI_FEMALE = "hi_female"
    HI_MALE = "hi_male"


@dataclass(frozen=True, slots=True)
class CustomVoice:
    """Cloned voice, identified server-side by its upload name."""

    name: str


Voice: TypeAlias = PresetVoice | CustomVoice

DEFAULT_VOICE: Voice = PresetVoice.FR_FEMALE
"""Confirmed by smoke test 2026-05-10: most natural for French narration."""


def voice_id(voice: Voice) -> str:
    """Return the string identifier expected by the TTS API."""
    if isinstance(voice, PresetVoice):
        return voice.value
    return voice.name
