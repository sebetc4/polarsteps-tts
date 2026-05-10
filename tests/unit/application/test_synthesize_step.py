from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from polarsteps_tts.application.use_cases import (
    SynthesizeStepCommand,
    SynthesizeStepUseCase,
)
from polarsteps_tts.domain.entities import (
    AudioSegment,
    NarrationScript,
    PresetVoice,
    TextChunk,
)
from polarsteps_tts.domain.exceptions import TtsEngineError


def _make_segment(duration_seconds: float, sample_rate: int = 24000) -> AudioSegment:
    nbytes = int(sample_rate * duration_seconds) * 2  # 16-bit mono
    return AudioSegment(pcm=b"\x00" * nbytes, sample_rate=sample_rate)


class TestSynthesizeStepUseCase:
    def test_calls_engine_once_per_chunk(self) -> None:
        engine = MagicMock()
        engine.synthesize.return_value = _make_segment(0.5)

        script = NarrationScript(body=(TextChunk("Un."), TextChunk("Deux."), TextChunk("Trois.")))
        use_case = SynthesizeStepUseCase(engine)

        use_case.execute(SynthesizeStepCommand(script=script, voice=PresetVoice.FR_FEMALE))

        assert engine.synthesize.call_count == 3

    def test_returns_segments_in_chunk_order(self) -> None:
        engine = MagicMock()
        engine.synthesize.side_effect = [
            _make_segment(0.5),
            _make_segment(1.0),
            _make_segment(0.25),
        ]

        script = NarrationScript(body=(TextChunk("A"), TextChunk("B"), TextChunk("C")))
        result = SynthesizeStepUseCase(engine).execute(
            SynthesizeStepCommand(script=script, voice=PresetVoice.FR_FEMALE)
        )

        durations = [s.duration_seconds for s in result.segments]
        assert durations == pytest.approx([0.5, 1.0, 0.25])

    def test_aggregates_total_duration(self) -> None:
        engine = MagicMock()
        engine.synthesize.side_effect = [_make_segment(0.5), _make_segment(1.5)]

        script = NarrationScript(body=(TextChunk("A"), TextChunk("B")))
        result = SynthesizeStepUseCase(engine).execute(
            SynthesizeStepCommand(script=script, voice=PresetVoice.FR_FEMALE)
        )

        assert result.total_duration_seconds == pytest.approx(2.0)
        assert result.voice_used is PresetVoice.FR_FEMALE

    def test_propagates_engine_error(self) -> None:
        engine = MagicMock()
        engine.synthesize.side_effect = TtsEngineError("server down")

        script = NarrationScript(body=(TextChunk("A"),))
        with pytest.raises(TtsEngineError):
            SynthesizeStepUseCase(engine).execute(
                SynthesizeStepCommand(script=script, voice=PresetVoice.FR_FEMALE)
            )
