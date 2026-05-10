from __future__ import annotations

from datetime import UTC, datetime

from polarsteps_tts.domain.entities import Location, Step
from polarsteps_tts.domain.services import IntroGenerator


def _make_step(
    *,
    position: int,
    name: str,
    start_time: datetime,
    location: Location | None = None,
) -> Step:
    return Step(
        id=str(position),
        name=name,
        start_time=start_time,
        position=position,
        description="body",
        location=location,
    )


class TestIntroGenerator:
    def test_full_metadata(self) -> None:
        step = _make_step(
            position=5,
            name="Refuge des Mottets",
            start_time=datetime(2024, 7, 15, 10, 0, tzinfo=UTC),
            location=Location(name="Bourg-Saint-Maurice"),
        )
        intro = IntroGenerator().generate(step)
        assert (
            intro.text == "Étape 5 : Refuge des Mottets. Le 15 juillet 2024, à Bourg-Saint-Maurice."
        )

    def test_without_location_omits_a_clause(self) -> None:
        step = _make_step(
            position=1,
            name="Départ",
            start_time=datetime(2024, 7, 10, 8, 0, tzinfo=UTC),
        )
        intro = IntroGenerator().generate(step)
        assert intro.text == "Étape 1 : Départ. Le 10 juillet 2024."

    def test_without_name_uses_position_only(self) -> None:
        step = _make_step(
            position=12,
            name="",
            start_time=datetime(2024, 8, 2, 14, 0, tzinfo=UTC),
            location=Location(name="Tokyo"),
        )
        intro = IntroGenerator().generate(step)
        assert intro.text == "Étape 12. Le 2 août 2024, à Tokyo."

    def test_first_of_month_uses_ordinal(self) -> None:
        step = _make_step(
            position=3,
            name="Arrivée",
            start_time=datetime(2024, 9, 1, 9, 0, tzinfo=UTC),
        )
        intro = IntroGenerator().generate(step)
        assert intro.text == "Étape 3 : Arrivée. Le 1er septembre 2024."

    def test_strips_whitespace_in_name(self) -> None:
        step = _make_step(
            position=2,
            name="   Col du Tricot   ",
            start_time=datetime(2024, 7, 11, 0, 0, tzinfo=UTC),
        )
        intro = IntroGenerator().generate(step)
        assert "Col du Tricot" in intro.text
        assert "  " not in intro.text

    def test_location_with_detail_uses_display_name(self) -> None:
        step = _make_step(
            position=4,
            name="Halte",
            start_time=datetime(2024, 7, 14, 0, 0, tzinfo=UTC),
            location=Location(name="Chamonix", detail="Haute-Savoie"),
        )
        intro = IntroGenerator().generate(step)
        assert "Chamonix, Haute-Savoie" in intro.text

    def test_unicode_location_passes_through(self) -> None:
        step = _make_step(
            position=7,
            name="Lac",
            start_time=datetime(2024, 6, 20, 0, 0, tzinfo=UTC),
            location=Location(name="Þingvellir"),
        )
        intro = IntroGenerator().generate(step)
        assert "Þingvellir" in intro.text

    def test_each_month_renders_correctly(self) -> None:
        expected = [
            "janvier",
            "février",
            "mars",
            "avril",
            "mai",
            "juin",
            "juillet",
            "août",
            "septembre",
            "octobre",
            "novembre",
            "décembre",
        ]
        for i, label in enumerate(expected, start=1):
            step = _make_step(
                position=i,
                name="X",
                start_time=datetime(2024, i, 5, 0, 0, tzinfo=UTC),
            )
            intro = IntroGenerator().generate(step)
            assert label in intro.text, f"month {i} expected '{label}' in {intro.text!r}"
