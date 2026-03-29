"""Tests for fileshare path properties on SygenPaths."""

from __future__ import annotations

from pathlib import Path

from sygen_bot.workspace.paths import SygenPaths


class TestFilesharePaths:
    def test_uploads_dir(self, tmp_path: Path) -> None:
        paths = SygenPaths(sygen_home=tmp_path)
        assert paths.fileshare_uploads_dir == tmp_path / "fileshare" / "uploads"

    def test_downloads_dir(self, tmp_path: Path) -> None:
        paths = SygenPaths(sygen_home=tmp_path)
        assert paths.fileshare_downloads_dir == tmp_path / "fileshare" / "downloads"
