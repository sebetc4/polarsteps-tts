from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IntroSegment:
    """Spoken introduction generated from a step's metadata.

    Synthesized as a dedicated chunk and followed by a longer silence than
    inter-paragraph silences (cf. étape 5).
    """

    text: str

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("IntroSegment text cannot be empty")


@dataclass(frozen=True, slots=True)
class TextChunk:
    """A single piece of body text passed to the TTS engine in one call.

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
    """Full narration of a step: optional intro + ordered body chunks."""

    body: tuple[TextChunk, ...]
    intro: IntroSegment | None = None

    def __post_init__(self) -> None:
        if not self.body:
            raise ValueError("NarrationScript body must contain at least one chunk")

    def all_segments(self) -> tuple[str, ...]:
        """Return ordered TTS inputs (intro first when present, then body chunks)."""
        if self.intro is None:
            return tuple(c.text for c in self.body)
        return (self.intro.text, *(c.text for c in self.body))

    @classmethod
    def from_paragraphs(cls, text: str) -> NarrationScript:
        """Split on blank lines, drop empty paragraphs, no intro.

        Kept as a fast path for raw-text scenarios (debug, txt files). The
        nominal path goes through `PrepareNarrationUseCase` (étape 3).
        """
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            raise ValueError("Cannot build NarrationScript from empty text")
        return cls(body=tuple(TextChunk(text=p) for p in paragraphs), intro=None)
