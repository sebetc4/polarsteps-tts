from __future__ import annotations

import re
from dataclasses import dataclass

# Sentence boundary: end-of-sentence punctuation, then whitespace, then a
# capital letter (incl. accented). Look-around keeps the punctuation attached
# to the preceding sentence and the capital letter on the next one.
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-ÝŒÆ])")

_PARAGRAPH_BOUNDARY_RE = re.compile(r"\n\s*\n+")


@dataclass(frozen=True, slots=True)
class TextChunker:
    """Split text into chunks for TTS synthesis.

    Strategy: paragraph-first (`\\n\\n`), with a sentence-level fallback when
    a paragraph exceeds `max_chars`. Validated by smoke test 4.A — finer
    granularity breaks fluidity, monolithic flattens prosody.

    A sentence longer than `max_chars` is emitted as-is (we don't split
    mid-sentence). This is rare in practice for travel-journal prose.
    """

    max_chars: int = 3000

    def __post_init__(self) -> None:
        if self.max_chars <= 0:
            raise ValueError(f"max_chars must be positive, got {self.max_chars}")

    def chunk(self, text: str) -> tuple[str, ...]:
        paragraphs = [p.strip() for p in _PARAGRAPH_BOUNDARY_RE.split(text) if p.strip()]
        out: list[str] = []
        for paragraph in paragraphs:
            if len(paragraph) <= self.max_chars:
                out.append(paragraph)
            else:
                out.extend(self._split_long_paragraph(paragraph))
        return tuple(out)

    def _split_long_paragraph(self, paragraph: str) -> list[str]:
        sentences = _SENTENCE_BOUNDARY_RE.split(paragraph)
        if not sentences:
            return [paragraph]

        blocks: list[str] = []
        buffer = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            candidate = f"{buffer} {sentence}".strip() if buffer else sentence
            if len(candidate) <= self.max_chars:
                buffer = candidate
            else:
                if buffer:
                    blocks.append(buffer)
                buffer = sentence
        if buffer:
            blocks.append(buffer)
        return blocks
