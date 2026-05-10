from __future__ import annotations

import pytest

from polarsteps_tts.domain.services import TextChunker


class TestConstructor:
    def test_rejects_zero_max_chars(self) -> None:
        with pytest.raises(ValueError):
            TextChunker(max_chars=0)

    def test_rejects_negative_max_chars(self) -> None:
        with pytest.raises(ValueError):
            TextChunker(max_chars=-10)


class TestParagraphSplit:
    def test_short_text_returns_single_chunk(self) -> None:
        assert TextChunker().chunk("Une phrase courte.") == ("Une phrase courte.",)

    def test_splits_on_blank_lines(self) -> None:
        text = "Un.\n\nDeux.\n\nTrois."
        assert TextChunker().chunk(text) == ("Un.", "Deux.", "Trois.")

    def test_empty_paragraphs_dropped(self) -> None:
        text = "Un.\n\n   \n\nDeux."
        assert TextChunker().chunk(text) == ("Un.", "Deux.")

    def test_empty_text_returns_empty_tuple(self) -> None:
        assert TextChunker().chunk("") == ()

    def test_whitespace_only_returns_empty_tuple(self) -> None:
        assert TextChunker().chunk("\n\n   \n\n") == ()

    def test_paragraph_below_threshold_kept_whole(self) -> None:
        chunker = TextChunker(max_chars=200)
        text = "Phrase A. Phrase B. Phrase C."
        assert chunker.chunk(text) == (text,)


class TestSentenceFallback:
    def test_long_paragraph_split_into_sentences(self) -> None:
        chunker = TextChunker(max_chars=30)
        text = "Phrase un courte. Phrase deux. Phrase trois ici. Phrase quatre."
        chunks = chunker.chunk(text)
        # Each chunk must respect max_chars.
        assert all(len(c) <= 30 for c in chunks), chunks
        # Original sentences are preserved end-to-end (concat back equals input modulo spaces).
        rejoined = " ".join(chunks)
        assert "Phrase un courte" in rejoined
        assert "Phrase quatre" in rejoined

    def test_split_does_not_break_mid_sentence(self) -> None:
        chunker = TextChunker(max_chars=40)
        text = "Première phrase. Deuxième phrase ici. Troisième."
        chunks = chunker.chunk(text)
        for chunk in chunks:
            # Each emitted chunk should end with sentence-ending punctuation.
            assert chunk.rstrip()[-1] in ".!?", f"{chunk!r} does not end on sentence punctuation"

    def test_single_sentence_above_threshold_emitted_as_is(self) -> None:
        # When a single sentence exceeds max_chars we don't split mid-sentence;
        # we emit it as-is rather than mangling it.
        chunker = TextChunker(max_chars=20)
        text = "Une seule très longue phrase qui dépasse largement la limite imposée."
        chunks = chunker.chunk(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_groups_sentences_greedily(self) -> None:
        # Two short sentences that fit together stay grouped.
        chunker = TextChunker(max_chars=50)
        text = "Bonjour. Je vais bien. Et toi ? Très bien aussi."
        chunks = chunker.chunk(text)
        # All sentences fit within 50 chars total when joined → single chunk.
        assert len(chunks) == 1

    def test_handles_accented_capital_after_punctuation(self) -> None:
        chunker = TextChunker(max_chars=30)
        text = "Phrase un assez longue. Étude approfondie ici. Œuvre majeure aussi."
        chunks = chunker.chunk(text)
        # The accented capital ('É', 'Œ') must trigger sentence splits.
        assert len(chunks) >= 2


class TestRespectsMaxChars:
    def test_no_chunk_exceeds_max_chars_for_normal_input(self) -> None:
        chunker = TextChunker(max_chars=100)
        # 5 sentences of ~30 chars each = ~150 chars total, must split into
        # at least 2 chunks.
        text = (
            "Phrase un assez longue ici. "
            "Phrase deux assez longue ici. "
            "Phrase trois assez longue ici. "
            "Phrase quatre assez longue ici. "
            "Phrase cinq assez longue ici."
        )
        chunks = chunker.chunk(text)
        assert len(chunks) >= 2
        assert all(len(c) <= 100 for c in chunks), [len(c) for c in chunks]

    def test_paragraphs_never_combined(self) -> None:
        # Each paragraph emits independently — chunking within a paragraph
        # does not bleed into the next.
        chunker = TextChunker(max_chars=200)
        text = "Court premier.\n\nCourt deuxième."
        assert chunker.chunk(text) == ("Court premier.", "Court deuxième.")
