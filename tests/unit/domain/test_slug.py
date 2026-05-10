from __future__ import annotations

import pytest

from polarsteps_tts.domain.value_objects import Slug


class TestSlugConstructor:
    def test_accepts_valid_kebab_case(self) -> None:
        assert Slug("refuge-des-mottets").value == "refuge-des-mottets"

    def test_accepts_single_word(self) -> None:
        assert Slug("paris").value == "paris"

    def test_accepts_digits(self) -> None:
        assert Slug("etape-2024").value == "etape-2024"

    @pytest.mark.parametrize(
        "invalid",
        [
            "",
            "Refuge",  # uppercase
            "refuge_des_mottets",  # underscore
            "-leading",
            "trailing-",
            "double--dash",
            "café",  # accent
            "with space",
        ],
    )
    def test_rejects_invalid(self, invalid: str) -> None:
        with pytest.raises(ValueError, match="Invalid slug"):
            Slug(invalid)


class TestFromText:
    def test_basic_lowercase_kebab(self) -> None:
        assert Slug.from_text("Refuge des Mottets").value == "refuge-des-mottets"

    def test_strips_accents(self) -> None:
        assert Slug.from_text("Café à Aix").value == "cafe-a-aix"

    def test_strips_emojis_and_punctuation(self) -> None:
        assert Slug.from_text("Café à Aix-en-Provence ! 🏔️").value == "cafe-a-aix-en-provence"

    def test_collapses_consecutive_separators(self) -> None:
        assert Slug.from_text("hello   ---   world").value == "hello-world"

    def test_trims_leading_and_trailing_dashes(self) -> None:
        assert Slug.from_text("---hello---").value == "hello"

    def test_blank_text_falls_back_to_untitled(self) -> None:
        assert Slug.from_text("   ").value == "untitled"

    def test_only_punctuation_falls_back_to_untitled(self) -> None:
        assert Slug.from_text("!!! 🏔️ ???").value == "untitled"

    def test_truncates_to_max_length(self) -> None:
        long_text = "a" * 200
        assert len(Slug.from_text(long_text, max_length=20).value) <= 20

    def test_truncate_respects_word_boundary(self) -> None:
        result = Slug.from_text("hello world foo bar baz", max_length=15).value
        assert result == "hello-world-foo"

    def test_truncate_falls_back_when_first_word_too_long(self) -> None:
        result = Slug.from_text("supercalifragilisticexpialidocious", max_length=10).value
        assert result == "supercalif"

    def test_zero_max_length_raises(self) -> None:
        with pytest.raises(ValueError, match="max_length"):
            Slug.from_text("hello", max_length=0)

    def test_str_returns_value(self) -> None:
        assert str(Slug.from_text("Hello")) == "hello"

    def test_unicode_letter_dropped(self) -> None:
        # Cyrillic and CJK characters have no ASCII equivalent → dropped
        assert Slug.from_text("Москва").value == "untitled"

    def test_mixed_unicode_and_ascii(self) -> None:
        assert Slug.from_text("Tokyo 東京 trip").value == "tokyo-trip"
