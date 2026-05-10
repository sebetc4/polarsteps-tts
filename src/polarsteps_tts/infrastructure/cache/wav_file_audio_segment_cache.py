from __future__ import annotations

import io
import logging
import os
import re
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from polarsteps_tts.domain.entities import AudioSegment
from polarsteps_tts.domain.ports import AudioCacheKey, AudioSegmentCache

_logger = logging.getLogger(__name__)
_PATH_SAFE_RE = re.compile(r"[^A-Za-z0-9_.-]")


class WavFileAudioSegmentCache(AudioSegmentCache):
    """Stores audio segments as WAV files on disk, one file per cache key.

    Layout: `<root>/<voice_id>/<model_version>/<text_hash>-<options_hash>.wav`.

    The voice/model directories make manual inspection trivial (`ls cache/fr_female/`).
    Writes are atomic; reads silently invalidate corrupted files.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def get(self, key: AudioCacheKey) -> AudioSegment | None:
        path = self._path_for(key)
        if not path.exists():
            return None

        try:
            arr, sample_rate = sf.read(str(path), dtype="int16", always_2d=False)
        except (OSError, RuntimeError, ValueError) as e:
            _logger.warning("Corrupt audio cache file %s, invalidating: %s", path, e)
            self._unlink_silently(path)
            return None

        channels = 1 if arr.ndim == 1 else arr.shape[1]
        return AudioSegment(
            pcm=np.ascontiguousarray(arr).tobytes(),
            sample_rate=int(sample_rate),
            channels=channels,
        )

    def put(self, key: AudioCacheKey, segment: AudioSegment) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        arr = np.frombuffer(segment.pcm, dtype="<i2")
        if segment.channels > 1:
            arr = arr.reshape(-1, segment.channels)

        buffer = io.BytesIO()
        sf.write(buffer, arr, segment.sample_rate, format="WAV", subtype="PCM_16")
        self._atomic_write(path, buffer.getvalue())

    def _path_for(self, key: AudioCacheKey) -> Path:
        voice_dir = _path_safe(key.voice_id)
        model_dir = _path_safe(key.model_version)
        filename = f"{key.text_hash}-{key.options_hash}-{key.language}.wav"
        return self._root / voice_dir / model_dir / filename

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        fd, tmp_path = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(content)
            os.replace(tmp_path, path)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise

    @staticmethod
    def _unlink_silently(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            _logger.warning("Could not remove audio cache file %s", path)


def _path_safe(value: str) -> str:
    """Replace any path-unsafe character with `_` to preserve the layout invariant."""
    safe = _PATH_SAFE_RE.sub("_", value).strip("_")
    return safe or "unknown"
