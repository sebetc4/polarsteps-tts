from __future__ import annotations

from pathlib import Path

import pytest

from polarsteps_tts.infrastructure.storage import atomic_write_bytes, atomic_write_text


def test_atomic_write_bytes_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"
    atomic_write_bytes(target, b"hello")
    assert target.read_bytes() == b"hello"


def test_atomic_write_bytes_overwrites_existing(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"
    target.write_bytes(b"old")
    atomic_write_bytes(target, b"new")
    assert target.read_bytes() == b"new"


def test_atomic_write_does_not_leave_tempfile_on_success(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"
    atomic_write_bytes(target, b"hi")
    assert list(tmp_path.iterdir()) == [target]


def test_atomic_write_cleans_tempfile_on_failure(tmp_path: Path) -> None:
    target = tmp_path / "missing_dir" / "out.bin"
    with pytest.raises(FileNotFoundError):
        atomic_write_bytes(target, b"hi")
    assert list(tmp_path.iterdir()) == []


def test_atomic_write_text_encodes_utf8(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    atomic_write_text(target, "café ☕")
    assert target.read_text(encoding="utf-8") == "café ☕"
