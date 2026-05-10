from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from polarsteps_tts.domain.entities import AudioSegment


@dataclass(frozen=True, slots=True)
class AudioCacheKey:
    """Identifies a cached audio segment.

    Every field that influences the rendering must be part of the key,
    otherwise we'd serve stale audio after a model or voice change.
    `model_version` should embed model-level tweaks (e.g. `n_decoding_steps=64`)
    so a server-side parameter change invalidates the cache.
    """

    text_hash: str
    voice_id: str
    model_version: str
    language: str
    options_hash: str


class AudioSegmentCache(Protocol):
    """Storage of audio segments keyed by `AudioCacheKey`.

    Implementations must be fail-soft on read (return None on corruption)
    and atomic on write (no partial files visible).
    """

    def get(self, key: AudioCacheKey) -> AudioSegment | None: ...
    def put(self, key: AudioCacheKey, segment: AudioSegment) -> None: ...
