from __future__ import annotations

from unittest.mock import MagicMock

from polarsteps_tts.domain.entities import AudioSegment, Language, PresetVoice
from polarsteps_tts.domain.ports import AudioCacheKey, AudioSegmentCache
from polarsteps_tts.domain.value_objects import SynthesisOptions
from polarsteps_tts.infrastructure.tts import CachingTextToSpeechEngine

_MODEL = "voxtral-4b-tts-2603-ndecsteps64"


def _segment() -> AudioSegment:
    return AudioSegment(pcm=b"\x00" * 48000, sample_rate=24000)


class _MemoryCache(AudioSegmentCache):
    def __init__(self) -> None:
        self.store: dict[AudioCacheKey, AudioSegment] = {}

    def get(self, key: AudioCacheKey) -> AudioSegment | None:
        return self.store.get(key)

    def put(self, key: AudioCacheKey, segment: AudioSegment) -> None:
        self.store[key] = segment


class TestCachingTextToSpeechEngine:
    def test_cache_miss_calls_inner_and_caches(self) -> None:
        inner = MagicMock()
        inner.synthesize.return_value = _segment()
        cache = _MemoryCache()
        engine = CachingTextToSpeechEngine(inner, cache, model_version=_MODEL)

        engine.synthesize("Bonjour", PresetVoice.FR_FEMALE)

        assert inner.synthesize.call_count == 1
        assert len(cache.store) == 1

    def test_cache_hit_skips_inner(self) -> None:
        inner = MagicMock()
        inner.synthesize.return_value = _segment()
        cache = _MemoryCache()
        engine = CachingTextToSpeechEngine(inner, cache, model_version=_MODEL)

        engine.synthesize("Bonjour", PresetVoice.FR_FEMALE)
        engine.synthesize("Bonjour", PresetVoice.FR_FEMALE)

        assert inner.synthesize.call_count == 1

    def test_different_voices_produce_different_keys(self) -> None:
        inner = MagicMock()
        inner.synthesize.return_value = _segment()
        cache = _MemoryCache()
        engine = CachingTextToSpeechEngine(inner, cache, model_version=_MODEL)

        engine.synthesize("Bonjour", PresetVoice.FR_FEMALE)
        engine.synthesize("Bonjour", PresetVoice.FR_MALE)

        assert inner.synthesize.call_count == 2
        assert len(cache.store) == 2

    def test_different_text_produces_different_keys(self) -> None:
        inner = MagicMock()
        inner.synthesize.return_value = _segment()
        cache = _MemoryCache()
        engine = CachingTextToSpeechEngine(inner, cache, model_version=_MODEL)

        engine.synthesize("Bonjour", PresetVoice.FR_FEMALE)
        engine.synthesize("Salut", PresetVoice.FR_FEMALE)

        assert inner.synthesize.call_count == 2

    def test_different_options_produce_different_keys(self) -> None:
        inner = MagicMock()
        inner.synthesize.return_value = _segment()
        cache = _MemoryCache()
        engine = CachingTextToSpeechEngine(inner, cache, model_version=_MODEL)

        engine.synthesize("Bonjour", PresetVoice.FR_FEMALE, options=SynthesisOptions(speed=1.0))
        engine.synthesize("Bonjour", PresetVoice.FR_FEMALE, options=SynthesisOptions(speed=0.95))

        assert inner.synthesize.call_count == 2

    def test_different_model_version_produces_different_keys(self) -> None:
        inner = MagicMock()
        inner.synthesize.return_value = _segment()

        cache = _MemoryCache()
        CachingTextToSpeechEngine(inner, cache, model_version="m1").synthesize(
            "Bonjour", PresetVoice.FR_FEMALE
        )
        CachingTextToSpeechEngine(inner, cache, model_version="m2").synthesize(
            "Bonjour", PresetVoice.FR_FEMALE
        )

        assert inner.synthesize.call_count == 2
        assert len(cache.store) == 2

    def test_different_language_produces_different_keys(self) -> None:
        inner = MagicMock()
        inner.synthesize.return_value = _segment()
        cache = _MemoryCache()
        engine = CachingTextToSpeechEngine(inner, cache, model_version=_MODEL)

        engine.synthesize("Hello", PresetVoice.FR_FEMALE, language=Language.FRENCH)
        engine.synthesize("Hello", PresetVoice.FR_FEMALE, language=Language.ENGLISH)

        assert inner.synthesize.call_count == 2

    def test_health_check_delegates_to_inner(self) -> None:
        inner = MagicMock()
        cache = _MemoryCache()
        CachingTextToSpeechEngine(inner, cache, model_version=_MODEL).health_check()
        inner.health_check.assert_called_once()
