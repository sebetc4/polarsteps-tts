from __future__ import annotations

from polarsteps_tts.domain.entities import (
    DEFAULT_VOICE,
    CustomVoice,
    PresetVoice,
    voice_id,
)


class TestPresetVoice:
    def test_french_voices_use_correct_api_identifiers(self) -> None:
        assert PresetVoice.FR_FEMALE.value == "fr_female"
        assert PresetVoice.FR_MALE.value == "fr_male"

    def test_default_voice_is_french_female(self) -> None:
        assert DEFAULT_VOICE is PresetVoice.FR_FEMALE


class TestVoiceId:
    def test_preset_voice_returns_enum_value(self) -> None:
        assert voice_id(PresetVoice.FR_FEMALE) == "fr_female"

    def test_custom_voice_returns_user_given_name(self) -> None:
        assert voice_id(CustomVoice(name="my_clone")) == "my_clone"
