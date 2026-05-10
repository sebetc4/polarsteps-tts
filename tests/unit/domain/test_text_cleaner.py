from __future__ import annotations

from polarsteps_tts.domain.services import CleaningPolicy, TextCleaner


class TestEmojis:
    def test_strips_simple_emoji(self) -> None:
        assert TextCleaner().clean("Magnifique 🏔️ aujourd'hui") == "Magnifique aujourd'hui"

    def test_strips_multiple_emojis(self) -> None:
        assert TextCleaner().clean("Soleil ☀ et nuages ☁") == "Soleil et nuages"

    def test_strips_compound_emoji_zwj(self) -> None:
        # Family emoji uses ZWJ joiners.
        assert TextCleaner().clean("Famille 👨‍👩‍👧 heureuse") == "Famille heureuse"

    def test_strips_flag_emoji(self) -> None:
        assert TextCleaner().clean("Drapeau 🇫🇷 ici") == "Drapeau ici"

    def test_keeps_text_when_no_emoji(self) -> None:
        assert TextCleaner().clean("Aucun emoji ici.") == "Aucun emoji ici."


class TestUrls:
    def test_strips_https_url(self) -> None:
        assert TextCleaner().clean("Voir https://example.com pour plus") == "Voir pour plus"

    def test_strips_http_url(self) -> None:
        assert TextCleaner().clean("ici http://foo.bar/path?q=1") == "ici"

    def test_strips_url_with_path(self) -> None:
        cleaned = TextCleaner().clean("https://example.com/a/b et la suite")
        assert cleaned == "et la suite"


class TestAbbreviations:
    def test_expands_km(self) -> None:
        assert TextCleaner().clean("12 km de marche") == "12 kilomètres de marche"

    def test_expands_km_without_space(self) -> None:
        assert TextCleaner().clean("12km parcourus") == "12 kilomètres parcourus"

    def test_expands_meters(self) -> None:
        assert TextCleaner().clean("dénivelé 300 m total") == "dénivelé 300 mètres total"

    def test_does_not_expand_meters_inside_word(self) -> None:
        # 'kma' shouldn't trigger 'km' expansion (\b boundary).
        assert TextCleaner().clean("le kmag") == "le kmag"

    def test_expands_mm_before_m(self) -> None:
        assert TextCleaner().clean("200 mm de pluie") == "200 millimètres de pluie"

    def test_expands_cm(self) -> None:
        assert TextCleaner().clean("30 cm de neige") == "30 centimètres de neige"

    def test_expands_hour_composite(self) -> None:
        assert TextCleaner().clean("2h30 de montée") == "2 heures 30 de montée"

    def test_expands_bare_hours(self) -> None:
        assert TextCleaner().clean("3 h de pause") == "3 heures de pause"

    def test_expands_minutes(self) -> None:
        assert TextCleaner().clean("45 mn de descente") == "45 minutes de descente"

    def test_expands_min_variant(self) -> None:
        assert TextCleaner().clean("10 min de marche") == "10 minutes de marche"

    def test_expands_celsius(self) -> None:
        assert TextCleaner().clean("15°C ce matin") == "15 degrés ce matin"

    def test_expands_percent(self) -> None:
        assert TextCleaner().clean("90% d'humidité") == "90 pourcent d'humidité"

    def test_expands_first_ordinal(self) -> None:
        assert TextCleaner().clean("le 1er camp") == "le premier camp"

    def test_expands_first_ordinal_feminine(self) -> None:
        assert TextCleaner().clean("la 1re étape") == "la première étape"

    def test_expands_kilograms(self) -> None:
        assert TextCleaner().clean("sac de 12 kg") == "sac de 12 kilogrammes"

    def test_expands_ampersand(self) -> None:
        assert TextCleaner().clean("Alice & Bob") == "Alice et Bob"


class TestPunctuation:
    def test_collapses_multiple_dots_to_ellipsis(self) -> None:
        assert TextCleaner().clean("attendons.....") == "attendons..."

    def test_collapses_double_exclamation(self) -> None:
        assert TextCleaner().clean("Génial!!!") == "Génial!"

    def test_collapses_double_question(self) -> None:
        assert TextCleaner().clean("Vraiment???") == "Vraiment?"

    def test_keeps_single_punctuation(self) -> None:
        assert TextCleaner().clean("Bien. Pas mal! Vraiment?") == "Bien. Pas mal! Vraiment?"


class TestWhitespace:
    def test_collapses_multiple_spaces(self) -> None:
        assert TextCleaner().clean("trop    d'espace") == "trop d'espace"

    def test_strips_leading_trailing(self) -> None:
        assert TextCleaner().clean("   bordures   ") == "bordures"

    def test_preserves_paragraph_boundary(self) -> None:
        text = "Premier.\n\nDeuxième."
        assert TextCleaner().clean(text) == "Premier.\n\nDeuxième."

    def test_collapses_intra_paragraph_newline(self) -> None:
        text = "Ligne 1\nligne 2\nligne 3"
        assert TextCleaner().clean(text) == "Ligne 1 ligne 2 ligne 3"

    def test_collapses_more_than_two_newlines_to_paragraph(self) -> None:
        text = "Un.\n\n\n\nDeux."
        assert TextCleaner().clean(text) == "Un.\n\nDeux."

    def test_drops_empty_paragraphs(self) -> None:
        text = "Un.\n\n   \n\nDeux."
        assert TextCleaner().clean(text) == "Un.\n\nDeux."


class TestPolicyToggles:
    def test_disable_strip_emojis(self) -> None:
        cleaner = TextCleaner(policy=CleaningPolicy(strip_emojis=False))
        assert cleaner.clean("Salut 🏔️") == "Salut 🏔️"

    def test_disable_strip_urls(self) -> None:
        cleaner = TextCleaner(policy=CleaningPolicy(strip_urls=False))
        assert "https://example.com" in cleaner.clean("voir https://example.com fin")

    def test_disable_expand_abbreviations(self) -> None:
        cleaner = TextCleaner(policy=CleaningPolicy(expand_abbreviations=False))
        assert cleaner.clean("12 km") == "12 km"

    def test_disable_normalize_whitespace(self) -> None:
        cleaner = TextCleaner(policy=CleaningPolicy(normalize_whitespace=False))
        # Without normalization, double spaces survive (only outer strip applied).
        assert cleaner.clean("a   b") == "a   b"


class TestIdempotence:
    def test_clean_is_idempotent_on_complex_input(self) -> None:
        text = "Magnifique 🏔️!!! 12 km à pied... voir https://example.com\n\nFin."
        cleaner = TextCleaner()
        once = cleaner.clean(text)
        twice = cleaner.clean(once)
        assert once == twice

    def test_clean_is_idempotent_on_paragraph_text(self) -> None:
        text = "Premier paragraphe.\n\nDeuxième."
        cleaner = TextCleaner()
        assert cleaner.clean(cleaner.clean(text)) == cleaner.clean(text)
