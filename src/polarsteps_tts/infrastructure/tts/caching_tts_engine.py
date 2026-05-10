from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from polarsteps_tts.domain.entities import (
    AudioSegment,
    Language,
    Voice,
    voice_id,
)
from polarsteps_tts.domain.ports import (
    AudioCacheKey,
    AudioSegmentCache,
    TextToSpeechEngine,
)
from polarsteps_tts.domain.value_objects import DEFAULT_SYNTHESIS_OPTIONS, SynthesisOptions


class CachingTextToSpeechEngine(TextToSpeechEngine):
    """Decorator that memoizes synthesis results by content key.

    Same role as `CachedTripRepository` for the Polarsteps fetcher: the
    underlying engine has no idea the cache exists. `model_version` must
    embed any server-side tweak that changes audio output (e.g. the value
    of `n_decoding_steps` configured in `params.json`) so a backend retune
    invalidates cached entries.
    """

    def __init__(
        self,
        inner: TextToSpeechEngine,
        cache: AudioSegmentCache,
        model_version: str,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._model_version = model_version

    def synthesize(
        self,
        text: str,
        voice: Voice,
        language: Language = Language.FRENCH,
        options: SynthesisOptions = DEFAULT_SYNTHESIS_OPTIONS,
    ) -> AudioSegment:
        key = AudioCacheKey(
            text_hash=_sha256(text),
            voice_id=voice_id(voice),
            model_version=self._model_version,
            language=language.value,
            options_hash=_options_hash(options),
        )

        cached = self._cache.get(key)
        if cached is not None:
            return cached

        segment = self._inner.synthesize(text, voice, language, options)
        self._cache.put(key, segment)
        return segment

    def health_check(self) -> None:
        self._inner.health_check()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _options_hash(options: SynthesisOptions) -> str:
    serialized = json.dumps(asdict(options), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
