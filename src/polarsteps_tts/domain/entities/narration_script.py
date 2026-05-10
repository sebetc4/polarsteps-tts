from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextChunk:
    """A single piece of text passed to the TTS engine in one call.

    Order matters: chunks are concatenated in declaration order. The boundary
    between two chunks creates a small inter-chunk silence at post-process
    time (étape 5) — confirmed mandatory by the 4.A smoke test.
    """

    text: str

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("TextChunk text cannot be empty")


@dataclass(frozen=True, slots=True)
class NarrationScript:
    """Minimal stub for the étape 3 output: an ordered list of TTS chunks.

    Will be enriched by étape 3 (intro segment, language, voice override per chunk).
    Kept minimal here so étape 4 can ship without blocking on étape 3.
    """

    chunks: tuple[TextChunk, ...]

    def __post_init__(self) -> None:
        if not self.chunks:
            raise ValueError("NarrationScript must contain at least one chunk")

    @classmethod
    def from_paragraphs(cls, text: str) -> NarrationScript:
        """Split on blank lines (paragraph boundary), drop empty paragraphs.

        Paragraph-level chunking is the quality strategy validated in 4.A:
        finer (sentence) breaks fluidity, monolithic flattens prosody.
        """
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            raise ValueError("Cannot build NarrationScript from empty text")
        return cls(chunks=tuple(TextChunk(text=p) for p in paragraphs))
