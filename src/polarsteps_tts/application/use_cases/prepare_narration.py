from __future__ import annotations

from dataclasses import dataclass

from polarsteps_tts.domain.entities import NarrationScript, Step, TextChunk
from polarsteps_tts.domain.exceptions import EmptyStepTextError
from polarsteps_tts.domain.services import IntroGenerator, TextChunker, TextCleaner


@dataclass(frozen=True, slots=True)
class PrepareNarrationCommand:
    step: Step
    include_intro: bool = True


@dataclass(frozen=True, slots=True)
class PrepareNarrationUseCase:
    """Build a `NarrationScript` from a `Step` (intro + cleaned + chunked body).

    Pure orchestration: no port dependencies, deterministic given the same
    services and step.
    """

    intro_generator: IntroGenerator
    text_cleaner: TextCleaner
    text_chunker: TextChunker

    def execute(self, command: PrepareNarrationCommand) -> NarrationScript:
        if not command.step.has_text:
            raise EmptyStepTextError(
                f"Step {command.step.position} ('{command.step.name}') has no text"
            )

        cleaned = self.text_cleaner.clean(command.step.description or "")
        chunks = self.text_chunker.chunk(cleaned)
        if not chunks:
            raise EmptyStepTextError(
                f"Step {command.step.position} ('{command.step.name}') "
                "has no narratable content after cleaning"
            )

        intro = self.intro_generator.generate(command.step) if command.include_intro else None
        return NarrationScript(
            body=tuple(TextChunk(text=c) for c in chunks),
            intro=intro,
        )
