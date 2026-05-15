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

    def test_expands_speed_km_per_hour(self) -> None:
        # km/h must be caught before plain km, otherwise "km" gets eaten and
        # we'd be left with "80 kilomètres/h".
        assert TextCleaner().clean("rafales à 80 km/h") == ("rafales à 80 kilomètres-heure")

    def test_expands_speed_km_per_hour_no_space(self) -> None:
        assert TextCleaner().clean("vitesse 7km/h") == "vitesse 7 kilomètres-heure"

    def test_expands_d_plus(self) -> None:
        # D+ = dénivelé positif (cycling jargon).
        assert TextCleaner().clean("910m de D+") == "910 mètres de dénivelé positif"

    def test_expands_d_plus_with_space(self) -> None:
        assert TextCleaner().clean("100 m de D +") == "100 mètres de dénivelé positif"

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


class TestListMarkers:
    def test_dash_bullet_creates_sentence_boundary(self) -> None:
        cleaner = TextCleaner()
        assert cleaner.clean("Intro\n- Option 1") == "Intro. Option 1"

    def test_multiple_dash_bullets_each_become_sentences(self) -> None:
        cleaner = TextCleaner()
        text = "Intro\n- Option 1 : foo.\n- Option 2 : bar."
        # "Intro" → ". " (no terminator yet) ; "foo." → terminator-aware, no
        # extra period inserted before "Option 2".
        assert cleaner.clean(text) == "Intro. Option 1 : foo. Option 2 : bar."

    def test_unicode_bullet_is_handled(self) -> None:
        cleaner = TextCleaner()
        assert cleaner.clean("Liste\n• Premier\n• Second") == "Liste. Premier. Second"

    def test_asterisk_bullet_is_handled(self) -> None:
        cleaner = TextCleaner()
        assert cleaner.clean("À faire\n* Un\n* Deux") == "À faire. Un. Deux"

    def test_keeps_compound_words_in_list_item(self) -> None:
        # The list-marker rule strips the leading bullet but composés mid-text
        # (rendez-vous, semble-t-il) must survive intact.
        cleaner = TextCleaner()
        assert cleaner.clean("- rendez-vous semble-t-il fois-ci") == (
            "rendez-vous semble-t-il fois-ci"
        )

    def test_leading_bullet_at_text_start_is_stripped(self) -> None:
        # First bullet: leading strip (no newline before).
        # Second bullet: previous line ends with `.` → terminator-aware, no
        # extra period inserted.
        cleaner = TextCleaner()
        assert cleaner.clean("- Premier item.\n- Second.") == "Premier item. Second."

    def test_terminator_aware_no_extra_period_after_period(self) -> None:
        # Line ends with "." → bullet should not add another period.
        cleaner = TextCleaner()
        assert cleaner.clean("Intro.\n- Option 1") == "Intro. Option 1"

    def test_terminator_aware_no_extra_period_after_colon(self) -> None:
        # Line ends with ":" → bullet should keep colon, no orphan period.
        cleaner = TextCleaner()
        assert cleaner.clean("Voici les options :\n- Option 1") == ("Voici les options : Option 1")

    def test_terminator_aware_handles_nbsp_before_newline(self) -> None:
        # French texts often have NBSP `\xa0` after `:` and before `\n`.
        cleaner = TextCleaner()
        text = "deux possibilités :\xa0\n- Option 1"
        assert cleaner.clean(text) == "deux possibilités : Option 1"

    def test_terminator_aware_after_question_mark(self) -> None:
        cleaner = TextCleaner()
        assert cleaner.clean("Question?\n- Réponse") == "Question? Réponse"

    def test_terminator_aware_after_exclamation(self) -> None:
        cleaner = TextCleaner()
        assert cleaner.clean("Surprise!\n- Détail") == "Surprise! Détail"


class TestInlineDashes:
    def test_replaces_separator_dash_with_comma(self) -> None:
        cleaner = TextCleaner()
        # All-caps normalization also kicks in → "BARILOCHE" → "Bariloche".
        assert cleaner.clean("BARILOCHE - ZAPALA") == "Bariloche, Zapala"

    def test_replaces_em_dash(self) -> None:
        cleaner = TextCleaner()
        assert cleaner.clean("Lima — Cuzco") == "Lima, Cuzco"

    def test_replaces_en_dash(self) -> None:
        cleaner = TextCleaner()
        assert cleaner.clean("Paris – Lyon") == "Paris, Lyon"  # noqa: RUF001

    def test_keeps_compound_word_with_hyphen(self) -> None:
        # No spaces around the dash → real composé, must stay intact.
        cleaner = TextCleaner()
        assert cleaner.clean("rendez-vous semble-t-il fois-ci") == (
            "rendez-vous semble-t-il fois-ci"
        )

    def test_replaces_only_one_dash_per_position(self) -> None:
        cleaner = TextCleaner()
        # Multiple dashes between spaces still collapse to one comma.
        assert cleaner.clean("A -- B") == "A, B"

    def test_handles_dash_with_irregular_whitespace(self) -> None:
        cleaner = TextCleaner()
        assert cleaner.clean("A  -   B") == "A, B"


class TestDayHeaderExpansion:
    def test_expands_jour_1_to_premier(self) -> None:
        cleaner = TextCleaner()
        assert cleaner.clean("Jour 1 : Départ matinal") == "Premier jour : Départ matinal"

    def test_expands_jour_5_to_cinquieme(self) -> None:
        cleaner = TextCleaner()
        assert cleaner.clean("Jour 5 : suite du voyage") == "Cinquième jour : suite du voyage"

    def test_expands_uppercase_jour(self) -> None:
        # Pipeline runs all-caps norm before day-header expansion, so JOUR
        # is title-cased first, then matched.
        cleaner = TextCleaner()
        assert cleaner.clean("JOUR 3 :") == "Troisième jour :"

    def test_expands_mid_text(self) -> None:
        cleaner = TextCleaner()
        assert cleaner.clean("Hier, jour 7 du voyage") == "Hier, septième jour du voyage"

    def test_handles_two_digit_days(self) -> None:
        cleaner = TextCleaner()
        assert cleaner.clean("Jour 21 :") == "Vingt et unième jour :"
        assert cleaner.clean("Jour 30 :") == "Trentième jour :"

    def test_keeps_unknown_day_number(self) -> None:
        # Out of table → unchanged (graceful degradation).
        cleaner = TextCleaner()
        assert cleaner.clean("Jour 99 : suite") == "Jour 99 : suite"

    def test_does_not_match_aujourdhui(self) -> None:
        # "Aujourd'hui" must not be matched as "...jour <digit>".
        cleaner = TextCleaner()
        assert cleaner.clean("Aujourd'hui 3 mai") == "Aujourd'hui 3 mai"


class TestAllCapsNormalization:
    def test_titlecases_all_caps_word_4_chars(self) -> None:
        # Use "ETAPE" to test pure title-casing without triggering day-header
        # expansion (which would also rewrite "JOUR 1" → "Premier jour").
        cleaner = TextCleaner()
        assert cleaner.clean("ETAPE finale") == "Etape finale"

    def test_titlecases_long_all_caps_word(self) -> None:
        cleaner = TextCleaner()
        assert cleaner.clean("BARILOCHE est belle") == "Bariloche est belle"

    def test_keeps_short_acronyms_2_chars(self) -> None:
        cleaner = TextCleaner()
        assert cleaner.clean("Le GR 20") == "Le GR 20"

    def test_keeps_short_acronyms_3_chars(self) -> None:
        cleaner = TextCleaner()
        assert cleaner.clean("La PCT et le TMB") == "La PCT et le TMB"

    def test_handles_accented_caps(self) -> None:
        cleaner = TextCleaner()
        assert cleaner.clean("CÔNDORES vol haut") == "Côndores vol haut"

    def test_normalises_multiple_caps_words(self) -> None:
        cleaner = TextCleaner()
        # Side effect: dash separator also normalised.
        assert cleaner.clean("CALETA GONZALO - SANTA BÁRBARA") == ("Caleta Gonzalo, Santa Bárbara")

    def test_does_not_touch_normal_capitalised_words(self) -> None:
        cleaner = TextCleaner()
        assert cleaner.clean("Bariloche est belle") == "Bariloche est belle"


class TestPolicyToggles:
    def test_disable_strip_emojis(self) -> None:
        cleaner = TextCleaner(policy=CleaningPolicy(strip_emojis=False))
        assert cleaner.clean("Salut 🏔️") == "Salut 🏔️"

    def test_disable_strip_urls(self) -> None:
        cleaner = TextCleaner(policy=CleaningPolicy(strip_urls=False))
        assert "https://example.com" in cleaner.clean("voir https://example.com fin")

    def test_disable_strip_list_markers(self) -> None:
        cleaner = TextCleaner(policy=CleaningPolicy(strip_list_markers=False))
        assert cleaner.clean("Intro:\n- Option 1") == "Intro: - Option 1"

    def test_disable_normalize_inline_dashes(self) -> None:
        cleaner = TextCleaner(
            policy=CleaningPolicy(normalize_inline_dashes=False, normalize_all_caps=False)
        )
        assert cleaner.clean("BARILOCHE - ZAPALA") == "BARILOCHE - ZAPALA"

    def test_disable_normalize_all_caps(self) -> None:
        cleaner = TextCleaner(policy=CleaningPolicy(normalize_all_caps=False))
        assert cleaner.clean("BARILOCHE est belle") == "BARILOCHE est belle"

    def test_disable_expand_day_headers(self) -> None:
        cleaner = TextCleaner(policy=CleaningPolicy(expand_day_headers=False))
        assert cleaner.clean("Jour 1 : départ") == "Jour 1 : départ"

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
