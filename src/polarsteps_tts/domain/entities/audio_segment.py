from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AudioSegment:
    """Raw audio block in memory, independent from the final encoding.

    16-bit signed PCM is the pivot: easy to concatenate, lossless,
    accepted as-is by ffmpeg for the final MP3 step.
    """

    pcm: bytes
    sample_rate: int
    channels: int = 1

    @property
    def duration_seconds(self) -> float:
        bytes_per_sample = 2 * self.channels  # 16-bit
        return len(self.pcm) / (self.sample_rate * bytes_per_sample)
