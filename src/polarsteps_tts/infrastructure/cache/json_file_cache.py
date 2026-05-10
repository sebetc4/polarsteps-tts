from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polarsteps_tts.domain.ports import CachedPayload, TripPayloadCache
from polarsteps_tts.domain.value_objects import TripId

_logger = logging.getLogger(__name__)


class JsonFileCache(TripPayloadCache):
    """Stores Polarsteps payloads as one JSON file per trip under a root directory.

    File layout: `<root>/<trip_id>.json` containing
    `{"fetched_at": "<iso>", "payload": {...}}`.

    Writes are atomic (write to a temp file in the same directory, then rename).
    Reads are defensive: a corrupted or schema-incompatible file is silently
    invalidated and treated as a miss.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def get(self, trip_id: TripId) -> CachedPayload | None:
        path = self._path_for(trip_id)
        if not path.exists():
            return None

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(raw["fetched_at"])
            payload = raw["payload"]
            if not isinstance(payload, dict):
                raise ValueError("payload is not a JSON object")
        except (OSError, ValueError, KeyError, TypeError) as e:
            _logger.warning("Corrupt cache file %s, invalidating: %s", path, e)
            self._unlink_silently(path)
            return None

        return CachedPayload(payload=payload, fetched_at=fetched_at)

    def put(self, trip_id: TripId, payload: dict[str, Any]) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._path_for(trip_id)
        record = {
            "fetched_at": datetime.now(UTC).isoformat(),
            "payload": payload,
        }
        self._atomic_write(path, json.dumps(record, ensure_ascii=False))

    def invalidate(self, trip_id: TripId) -> None:
        self._unlink_silently(self._path_for(trip_id))

    def _path_for(self, trip_id: TripId) -> Path:
        return self._root / f"{trip_id}.json"

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        fd, tmp_path = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
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
            _logger.warning("Could not remove cache file %s", path)
