from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from polarsteps_tts.domain.value_objects import TripId
from polarsteps_tts.infrastructure.cache import JsonFileCache


@pytest.fixture
def cache(tmp_path: Path) -> JsonFileCache:
    return JsonFileCache(tmp_path / "cache")


class TestJsonFileCache:
    def test_get_returns_none_when_missing(self, cache: JsonFileCache) -> None:
        assert cache.get(TripId("42")) is None

    def test_put_then_get_returns_payload(self, cache: JsonFileCache) -> None:
        payload = {"id": 42, "name": "Test", "all_steps": []}
        cache.put(TripId("42"), payload)

        cached = cache.get(TripId("42"))
        assert cached is not None
        assert cached.payload == payload
        assert cached.fetched_at.tzinfo is not None
        # written within the last few seconds
        assert datetime.now(UTC) - cached.fetched_at < timedelta(seconds=5)

    def test_put_overwrites_existing(self, cache: JsonFileCache) -> None:
        cache.put(TripId("42"), {"id": 42, "version": 1})
        cache.put(TripId("42"), {"id": 42, "version": 2})

        cached = cache.get(TripId("42"))
        assert cached is not None
        assert cached.payload["version"] == 2

    def test_invalidate_removes_file(self, cache: JsonFileCache, tmp_path: Path) -> None:
        cache.put(TripId("42"), {"id": 42})
        assert (tmp_path / "cache" / "42.json").exists()

        cache.invalidate(TripId("42"))
        assert not (tmp_path / "cache" / "42.json").exists()
        assert cache.get(TripId("42")) is None

    def test_invalidate_missing_file_is_noop(self, cache: JsonFileCache) -> None:
        cache.invalidate(TripId("999"))  # must not raise

    def test_get_returns_none_and_deletes_file_when_corrupted(
        self, cache: JsonFileCache, tmp_path: Path
    ) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        bad_file = cache_dir / "42.json"
        bad_file.write_text("{not valid json")

        assert cache.get(TripId("42")) is None
        assert not bad_file.exists()

    def test_get_returns_none_when_schema_unexpected(
        self, cache: JsonFileCache, tmp_path: Path
    ) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        # missing 'fetched_at' key
        (cache_dir / "42.json").write_text('{"payload": {"id": 42}}')

        assert cache.get(TripId("42")) is None

    def test_atomic_write_does_not_leave_partial_file_on_failure(
        self, cache: JsonFileCache, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(*_args: object, **_kwargs: object) -> None:
            raise OSError("simulated rename failure")

        monkeypatch.setattr("os.replace", boom)
        with pytest.raises(OSError, match="simulated rename failure"):
            cache.put(TripId("42"), {"id": 42})

        cache_dir = tmp_path / "cache"
        # no final file, no leftover .tmp
        assert not (cache_dir / "42.json").exists()
        assert list(cache_dir.glob("*.tmp")) == []

    def test_creates_root_directory_lazily(self, tmp_path: Path) -> None:
        root = tmp_path / "deep" / "nested" / "cache"
        cache = JsonFileCache(root)
        assert not root.exists()

        cache.put(TripId("1"), {"id": 1})
        assert root.exists()
