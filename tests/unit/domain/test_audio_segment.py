from __future__ import annotations

from polarsteps_tts.domain.entities import AudioSegment


class TestAudioSegment:
    def test_duration_one_second_at_24khz_mono(self) -> None:
        # 24000 frames * 2 bytes/frame (16-bit mono) = 48000 bytes
        segment = AudioSegment(pcm=b"\x00" * 48000, sample_rate=24000, channels=1)
        assert segment.duration_seconds == 1.0

    def test_duration_half_second_at_24khz_mono(self) -> None:
        segment = AudioSegment(pcm=b"\x00" * 24000, sample_rate=24000, channels=1)
        assert segment.duration_seconds == 0.5

    def test_duration_for_stereo(self) -> None:
        # 24000 frames * 2 channels * 2 bytes = 96000 bytes for 1 second
        segment = AudioSegment(pcm=b"\x00" * 96000, sample_rate=24000, channels=2)
        assert segment.duration_seconds == 1.0

    def test_duration_empty_segment(self) -> None:
        segment = AudioSegment(pcm=b"", sample_rate=24000, channels=1)
        assert segment.duration_seconds == 0.0

    def test_segment_is_frozen(self) -> None:
        segment = AudioSegment(pcm=b"\x00" * 100, sample_rate=24000)
        try:
            segment.sample_rate = 48000  # type: ignore[misc]
        except (AttributeError, TypeError):
            return
        raise AssertionError("AudioSegment should be immutable")
