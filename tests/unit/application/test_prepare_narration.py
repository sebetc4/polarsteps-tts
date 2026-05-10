from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polarsteps_tts.application.use_cases import (
    PrepareNarrationCommand,
    PrepareNarrationUseCase,
)
from polarsteps_tts.domain.entities import Location, Step
from polarsteps_tts.domain.exceptions import EmptyStepTextError
from polarsteps_tts.domain.services import IntroGenerator, TextChunker, TextCleaner


def _use_case(*, max_chars: int = 3000) -> PrepareNarrationUseCase:
    return PrepareNarrationUseCase(
        intro_generator=IntroGenerator(),
        text_cleaner=TextCleaner(),
        text_chunker=TextChunker(max_chars=max_chars),
    )


def _make_step(
    *,
    position: int = 1,
    name: str = "Refuge",
    description: str | None = "Premier paragraphe.\n\nDeuxième paragraphe.",
    location: Location | None = None,
    start_time: datetime | None = None,
) -> Step:
    return Step(
        id=str(position),
        name=name,
        start_time=start_time or datetime(2024, 7, 15, 10, 0, tzinfo=UTC),
        position=position,
        description=description,
        location=location,
    )


class TestPrepareNarrationUseCase:
    def test_returns_script_with_intro_and_body(self) -> None:
        step = _make_step(location=Location(name="Bourg-Saint-Maurice"))
        script = _use_case().execute(PrepareNarrationCommand(step=step))

        assert script.intro is not None
        assert "Étape 1" in script.intro.text
        assert "Refuge" in script.intro.text
        assert len(script.body) == 2
        assert script.body[0].text == "Premier paragraphe."
        assert script.body[1].text == "Deuxième paragraphe."

    def test_without_intro_returns_script_with_intro_none(self) -> None:
        step = _make_step()
        script = _use_case().execute(PrepareNarrationCommand(step=step, include_intro=False))
        assert script.intro is None
        assert len(script.body) >= 1

    def test_cleans_emojis_and_abbreviations(self) -> None:
        step = _make_step(description="Marche de 12 km 🏔️ aujourd'hui.")
        script = _use_case().execute(PrepareNarrationCommand(step=step, include_intro=False))
        assert script.body[0].text == "Marche de 12 kilomètres aujourd'hui."

    def test_chunks_long_paragraphs(self) -> None:
        long_text = ("Phrase courte ici. " * 20).strip()
        step = _make_step(description=long_text)
        script = _use_case(max_chars=80).execute(
            PrepareNarrationCommand(step=step, include_intro=False)
        )
        # Chunked into multiple body chunks, each ≤ 80 chars.
        assert len(script.body) >= 2
        assert all(len(c.text) <= 80 for c in script.body)

    def test_raises_on_step_without_text(self) -> None:
        step = _make_step(description=None)
        with pytest.raises(EmptyStepTextError):
            _use_case().execute(PrepareNarrationCommand(step=step))

    def test_raises_on_whitespace_only_description(self) -> None:
        step = _make_step(description="   \n\n   ")
        with pytest.raises(EmptyStepTextError):
            _use_case().execute(PrepareNarrationCommand(step=step))

    def test_raises_when_text_empty_after_cleaning(self) -> None:
        # Description contains only emojis (and a URL) → nothing left to narrate.
        step = _make_step(description="🏔️🌲🍂 https://example.com")
        with pytest.raises(EmptyStepTextError):
            _use_case().execute(PrepareNarrationCommand(step=step))

    def test_intro_uses_step_metadata(self) -> None:
        step = _make_step(
            position=12,
            name="Lac glaciaire",
            location=Location(name="Tokyo"),
            start_time=datetime(2024, 8, 2, 0, 0, tzinfo=UTC),
        )
        script = _use_case().execute(PrepareNarrationCommand(step=step))
        assert script.intro is not None
        assert script.intro.text == ("Étape 12 : Lac glaciaire. Le 2 août 2024, à Tokyo.")
