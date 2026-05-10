from __future__ import annotations

import pytest

from polarsteps_tts.domain.entities import NarrationScript, TextChunk


class TestTextChunk:
    def test_rejects_empty_text(self) -> None:
        with pytest.raises(ValueError):
            TextChunk(text="")

    def test_rejects_whitespace_only_text(self) -> None:
        with pytest.raises(ValueError):
            TextChunk(text="   \n\t  ")


class TestNarrationScript:
    def test_rejects_empty_chunks(self) -> None:
        with pytest.raises(ValueError):
            NarrationScript(chunks=())

    def test_from_paragraphs_splits_on_blank_lines(self) -> None:
        text = "Premier paragraphe.\n\nDeuxième paragraphe.\n\nTroisième."
        script = NarrationScript.from_paragraphs(text)

        assert len(script.chunks) == 3
        assert script.chunks[0].text == "Premier paragraphe."
        assert script.chunks[1].text == "Deuxième paragraphe."
        assert script.chunks[2].text == "Troisième."

    def test_from_paragraphs_skips_empty_paragraphs(self) -> None:
        text = "Un.\n\n\n\nDeux.\n\n   \n\nTrois."
        script = NarrationScript.from_paragraphs(text)
        assert [c.text for c in script.chunks] == ["Un.", "Deux.", "Trois."]

    def test_from_paragraphs_single_paragraph_is_one_chunk(self) -> None:
        script = NarrationScript.from_paragraphs("Une seule phrase sans saut.")
        assert len(script.chunks) == 1

    def test_from_paragraphs_raises_on_empty_text(self) -> None:
        with pytest.raises(ValueError):
            NarrationScript.from_paragraphs("\n\n  \n\n")
