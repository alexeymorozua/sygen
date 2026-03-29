"""Tests for FileshareServer start/stop and HTTP routes."""

from __future__ import annotations

import asyncio
import urllib.request
from pathlib import Path

import pytest

from sygen_bot.fileshare.server import FileshareServer


@pytest.fixture()
def tmp_dirs(tmp_path: Path) -> tuple[Path, Path]:
    upload = tmp_path / "uploads"
    download = tmp_path / "downloads"
    upload.mkdir()
    download.mkdir()
    return upload, download


@pytest.fixture()
async def server(tmp_dirs: tuple[Path, Path]) -> FileshareServer:
    upload, download = tmp_dirs
    srv = FileshareServer(host="127.0.0.1", port=0, upload_dir=upload, download_dir=download)
    # Use port 0 to let OS assign a free port; override after bind.
    await srv.start()
    # Retrieve the actual bound port from the underlying server.
    actual_port = srv._server.server_address[1]
    srv._port = actual_port
    yield srv  # type: ignore[misc]
    await srv.stop()


class TestFileshareServer:
    async def test_start_stop(self, tmp_dirs: tuple[Path, Path]) -> None:
        upload, download = tmp_dirs
        srv = FileshareServer(host="127.0.0.1", port=0, upload_dir=upload, download_dir=download)
        await srv.start()
        assert srv._server is not None
        assert srv._thread is not None
        assert srv._thread.is_alive()
        await srv.stop()
        assert srv._server is None

    async def test_base_url(self, tmp_dirs: tuple[Path, Path]) -> None:
        upload, download = tmp_dirs
        srv = FileshareServer(host="127.0.0.1", port=9999, upload_dir=upload, download_dir=download)
        assert srv.base_url == "http://127.0.0.1:9999"

    async def test_index_page(self, server: FileshareServer) -> None:
        url = f"{server.base_url}/"
        resp = await asyncio.to_thread(urllib.request.urlopen, url)
        body = resp.read().decode()
        assert "Fileshare" in body
        assert resp.status == 200

    async def test_download_file(self, server: FileshareServer, tmp_dirs: tuple[Path, Path]) -> None:
        _, download = tmp_dirs
        test_file = download / "hello.txt"
        test_file.write_text("hello world")
        url = f"{server.base_url}/downloads/hello.txt"
        resp = await asyncio.to_thread(urllib.request.urlopen, url)
        assert resp.read() == b"hello world"

    async def test_download_alias(self, server: FileshareServer, tmp_dirs: tuple[Path, Path]) -> None:
        _, download = tmp_dirs
        test_file = download / "alias.txt"
        test_file.write_text("alias content")
        # /download/ (singular) should also work
        url = f"{server.base_url}/download/alias.txt"
        resp = await asyncio.to_thread(urllib.request.urlopen, url)
        assert resp.read() == b"alias content"

    async def test_404(self, server: FileshareServer) -> None:
        url = f"{server.base_url}/nonexistent"
        with pytest.raises(urllib.error.HTTPError, match="404"):
            await asyncio.to_thread(urllib.request.urlopen, url)

    async def test_path_traversal_blocked(self, server: FileshareServer) -> None:
        url = f"{server.base_url}/downloads/../../etc/passwd"
        with pytest.raises(urllib.error.HTTPError, match="403"):
            await asyncio.to_thread(urllib.request.urlopen, url)
