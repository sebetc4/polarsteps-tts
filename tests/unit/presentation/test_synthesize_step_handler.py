from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from polarsteps_tts.domain.entities import AudioSegment
from polarsteps_tts.presentation.handlers.synthesize_step_handler import (
    INTER_CHUNK_SILENCE_SECONDS,
    LEADING_SILENCE_SECONDS,
    TRAILING_SILENCE_SECONDS,
    _write_track,
)

_SAMPLE_RATE = 24000


def _segment(duration_seconds: float, value: int = 1000) -> AudioSegment:
    """Build a non-zero PCM segment so we can distinguish it from silence."""
    n = int(_SAMPLE_RATE * duration_seconds)
    pcm = np.full(n, value, dtype="<i2").tobytes()
    return AudioSegment(pcm=pcm, sample_rate=_SAMPLE_RATE, channels=1)


def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    data, sr = sf.read(str(path), dtype="int16", always_2d=False)
    return data, sr


class TestWriteWavWithSilences:
    def test_writes_leading_silence(self, tmp_path: Path) -> None:
        out = tmp_path / "track.wav"
        _write_track(out, (_segment(0.1),), INTER_CHUNK_SILENCE_SECONDS, output_format="wav")

        data, sr = _read_wav(out)
        leading_n = int(sr * LEADING_SILENCE_SECONDS)
        assert np.all(data[:leading_n] == 0)
        # Sample just after the leading silence is the segment's first sample.
        assert data[leading_n] != 0

    def test_writes_trailing_silence(self, tmp_path: Path) -> None:
        out = tmp_path / "track.wav"
        _write_track(out, (_segment(0.1),), INTER_CHUNK_SILENCE_SECONDS, output_format="wav")

        data, sr = _read_wav(out)
        trailing_n = int(sr * TRAILING_SILENCE_SECONDS)
        assert np.all(data[-trailing_n:] == 0)
        # Sample just before the trailing silence is still the segment.
        assert data[-trailing_n - 1] != 0

    def test_inter_chunk_silence_between_segments(self, tmp_path: Path) -> None:
        out = tmp_path / "track.wav"
        # Two distinct segments so we can detect the silence boundary.
        seg_a = _segment(0.1, value=1000)
        seg_b = _segment(0.1, value=2000)
        _write_track(out, (seg_a, seg_b), INTER_CHUNK_SILENCE_SECONDS, output_format="wav")

        data, sr = _read_wav(out)
        leading_n = int(sr * LEADING_SILENCE_SECONDS)
        seg_a_n = int(sr * 0.1)
        inter_n = int(sr * INTER_CHUNK_SILENCE_SECONDS)
        # Leading silence: zeros.
        assert np.all(data[:leading_n] == 0)
        # Segment A content.
        seg_a_slice = data[leading_n : leading_n + seg_a_n]
        assert np.all(seg_a_slice == 1000)
        # Inter-chunk silence: zeros.
        inter_slice = data[leading_n + seg_a_n : leading_n + seg_a_n + inter_n]
        assert np.all(inter_slice == 0)
        # Segment B content.
        b_start = leading_n + seg_a_n + inter_n
        seg_b_slice = data[b_start : b_start + seg_a_n]
        assert np.all(seg_b_slice == 2000)

    def test_total_duration_is_padding_plus_segments(self, tmp_path: Path) -> None:
        out = tmp_path / "track.wav"
        _write_track(
            out, (_segment(0.5), _segment(0.3)), INTER_CHUNK_SILENCE_SECONDS, output_format="wav"
        )

        data, sr = _read_wav(out)
        expected_seconds = (
            LEADING_SILENCE_SECONDS
            + 0.5
            + INTER_CHUNK_SILENCE_SECONDS
            + 0.3
            + TRAILING_SILENCE_SECONDS
        )
        actual_seconds = len(data) / sr
        assert abs(actual_seconds - expected_seconds) < 1e-3

    def test_overrides_padding_via_kwargs(self, tmp_path: Path) -> None:
        out = tmp_path / "track.wav"
        _write_track(
            out,
            (_segment(0.1),),
            INTER_CHUNK_SILENCE_SECONDS,
            output_format="wav",
            leading_silence_seconds=0.0,
            trailing_silence_seconds=0.0,
        )
        data, _sr = _read_wav(out)
        # No padding → first/last samples are content.
        assert data[0] != 0
        assert data[-1] != 0

    def test_empty_segments_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="empty"):
            _write_track(
                tmp_path / "track.wav", (), INTER_CHUNK_SILENCE_SECONDS, output_format="wav"
            )
