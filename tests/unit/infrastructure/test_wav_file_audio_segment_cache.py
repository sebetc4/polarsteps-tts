from __future__ import annotations

from pathlib import Path

import numpy as np

from polarsteps_tts.domain.entities import AudioSegment
from polarsteps_tts.domain.ports import AudioCacheKey
from polarsteps_tts.infrastructure.cache import WavFileAudioSegmentCache


def _key(
    text_hash: str = "abc",
    voice_id: str = "fr_female",
    model_version: str = "voxtral-4b-tts-2603-ndecsteps64",
    language: str = "fr",
    options_hash: str = "opt0",
) -> AudioCacheKey:
    return AudioCacheKey(
        text_hash=text_hash,
        voice_id=voice_id,
        model_version=model_version,
        language=language,
        options_hash=options_hash,
    )


def _segment(duration_seconds: float = 0.5, sample_rate: int = 24000) -> AudioSegment:
    samples = np.zeros(int(sample_rate * duration_seconds), dtype="<i2")
    return AudioSegment(pcm=samples.tobytes(), sample_rate=sample_rate)


class TestWavFileAudioSegmentCache:
    def test_get_returns_none_when_missing(self, tmp_path: Path) -> None:
        cache = WavFileAudioSegmentCache(tmp_path)
        assert cache.get(_key()) is None

    def test_put_then_get_returns_equivalent_segment(self, tmp_path: Path) -> None:
        cache = WavFileAudioSegmentCache(tmp_path)
        original = _segment(duration_seconds=0.5)

        cache.put(_key(), original)
        roundtripped = cache.get(_key())

        assert roundtripped is not None
        assert roundtripped.sample_rate == original.sample_rate
        assert roundtripped.channels == original.channels
        assert roundtripped.duration_seconds == original.duration_seconds
        assert roundtripped.pcm == original.pcm

    def test_layout_groups_by_voice_then_model(self, tmp_path: Path) -> None:
        cache = WavFileAudioSegmentCache(tmp_path)
        cache.put(_key(voice_id="fr_male", model_version="v1"), _segment())

        voice_dir = tmp_path / "fr_male"
        assert voice_dir.is_dir()
        model_dir = voice_dir / "v1"
        assert model_dir.is_dir()
        assert any(p.suffix == ".wav" for p in model_dir.iterdir())

    def test_different_voices_do_not_collide(self, tmp_path: Path) -> None:
        cache = WavFileAudioSegmentCache(tmp_path)
        cache.put(_key(voice_id="fr_female"), _segment())
        cache.put(_key(voice_id="fr_male"), _segment())

        assert (tmp_path / "fr_female").is_dir()
        assert (tmp_path / "fr_male").is_dir()

    def test_corrupted_wav_returns_none_and_invalidates(self, tmp_path: Path) -> None:
        cache = WavFileAudioSegmentCache(tmp_path)
        cache.put(_key(), _segment())

        # corrupt the only file in the layout
        wav_files = list(tmp_path.rglob("*.wav"))
        assert len(wav_files) == 1
        wav_files[0].write_bytes(b"not a wav file")

        result = cache.get(_key())
        assert result is None
        assert not wav_files[0].exists()

    def test_unsafe_voice_name_is_sanitized(self, tmp_path: Path) -> None:
        cache = WavFileAudioSegmentCache(tmp_path)
        cache.put(_key(voice_id="../../etc/passwd"), _segment())

        # No traversal: file lives strictly under tmp_path
        for p in tmp_path.rglob("*.wav"):
            assert tmp_path in p.parents
