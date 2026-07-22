"""Latest-report store: stable untimestamped names, overwrite-on-republish,
atomic replacement, and failure safety — pure filesystem, no database."""

import os

import pytest

from mip.reporting.latest import latest_dir, publish_latest


def test_publish_creates_directory_and_newline_terminated_file(tmp_path) -> None:
    path = publish_latest(tmp_path, "Portfolio.md", "# Report")
    assert path == tmp_path / "latest" / "Portfolio.md"
    assert path.read_text() == "# Report\n"  # newline appended only if missing
    assert publish_latest(tmp_path, "Portfolio.md", "# Report\n").read_text() == "# Report\n"


def test_repeated_publish_overwrites_in_place(tmp_path) -> None:
    publish_latest(tmp_path, "AMD.md", "old\n")
    path = publish_latest(tmp_path, "AMD.md", "new\n")
    assert path.read_text() == "new\n"
    # exactly one stable file — no timestamped or temp siblings
    assert [p.name for p in latest_dir(tmp_path).iterdir()] == ["AMD.md"]


def test_symbols_update_independently(tmp_path) -> None:
    publish_latest(tmp_path, "AMD.md", "amd v1\n")
    publish_latest(tmp_path, "NVDA.md", "nvda v1\n")
    publish_latest(tmp_path, "AMD.md", "amd v2\n")
    assert (latest_dir(tmp_path) / "NVDA.md").read_text() == "nvda v1\n"
    assert (latest_dir(tmp_path) / "AMD.md").read_text() == "amd v2\n"


def test_failed_replace_leaves_previous_intact_and_no_temp_files(tmp_path, monkeypatch) -> None:
    publish_latest(tmp_path, "AMD.md", "previous\n")

    def explode(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", explode)
    with pytest.raises(OSError, match="disk full"):
        publish_latest(tmp_path, "AMD.md", "half-written\n")
    assert (latest_dir(tmp_path) / "AMD.md").read_text() == "previous\n"
    assert [p.name for p in latest_dir(tmp_path).iterdir()] == ["AMD.md"]


def test_failed_write_before_any_previous_file(tmp_path, monkeypatch) -> None:
    def explode(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", explode)
    with pytest.raises(OSError):
        publish_latest(tmp_path, "NVDA.md", "content\n")
    assert list(latest_dir(tmp_path).iterdir()) == []  # nothing partial appears
