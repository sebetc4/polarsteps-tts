from __future__ import annotations

import pytest

from polarsteps_tts.domain.entities import IntroSegment, NarrationScript, TextChunk


class TestIntroSegment:
    def test_rejects_empty_text(self) -> None:
        with pytest.raises(ValueError):
            IntroSegment(text="")

    def test_rejects_whitespace_only_text(self) -> None:
        with pytest.raises(ValueError):
            IntroSegment(text="   \n\t  ")


class TestTextChunk:
    def test_rejects_empty_text(self) -> None:
        with pytest.raises(ValueError):
            TextChunk(text="")

    def test_rejects_whitespace_only_text(self) -> None:
        with pytest.raises(ValueError):
            TextChunk(text="   \n\t  ")


class TestNarrationScript:
    def test_rejects_empty_body(self) -> None:
        with pytest.raises(ValueError):
            NarrationScript(body=())

    def test_intro_defaults_to_none(self) -> None:
        script = NarrationScript(body=(TextChunk("Un."),))
        assert script.intro is None

    def test_accepts_intro_segment(self) -> None:
        intro = IntroSegment(text="Étape 1 : Départ.")
        script = NarrationScript(body=(TextChunk("Un."),), intro=intro)
        assert script.intro is intro

    def test_all_segments_omits_intro_when_none(self) -> None:
        script = NarrationScript(body=(TextChunk("A."), TextChunk("B.")))
        assert script.all_segments() == ("A.", "B.")

    def test_all_segments_places_intro_first(self) -> None:
        script = NarrationScript(
            body=(TextChunk("Corps."),),
            intro=IntroSegment(text="Intro orale."),
        )
        assert script.all_segments() == ("Intro orale.", "Corps.")


class TestFromParagraphs:
    def test_splits_on_blank_lines(self) -> None:
        text = "Premier paragraphe.\n\nDeuxième paragraphe.\n\nTroisième."
        script = NarrationScript.from_paragraphs(text)

        assert script.intro is None
        assert len(script.body) == 3
        assert script.body[0].text == "Premier paragraphe."
        assert script.body[1].text == "Deuxième paragraphe."
        assert script.body[2].text == "Troisième."

    def test_skips_empty_paragraphs(self) -> None:
        text = "Un.\n\n\n\nDeux.\n\n   \n\nTrois."
        script = NarrationScript.from_paragraphs(text)
        assert [c.text for c in script.body] == ["Un.", "Deux.", "Trois."]

    def test_single_paragraph_is_one_chunk(self) -> None:
        script = NarrationScript.from_paragraphs("Une seule phrase sans saut.")
        assert len(script.body) == 1

    def test_raises_on_empty_text(self) -> None:
        with pytest.raises(ValueError):
            NarrationScript.from_paragraphs("\n\n  \n\n")
