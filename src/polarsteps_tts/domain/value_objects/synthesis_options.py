from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SynthesisOptions:
    """Optional knobs that influence the audio rendering.

    All fields are part of the cache key in `AudioCacheKey` (4.F): changing
    any of them must invalidate cached audio. Defaults are no-ops so the
    options object can always be passed safely.

    `instructions` had no perceptible effect during the 2026-05-10 smoke test
    against Voxtral but is wired through for future model versions.
    """

    instructions: str | None = None
    speed: float = 1.0
    seed: int | None = None


DEFAULT_SYNTHESIS_OPTIONS = SynthesisOptions()
"""Module-level singleton — used as a safe default for function/dataclass args."""
