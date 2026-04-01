"""Tests for multi-source indexer."""

from __future__ import annotations

from pathlib import Path

import pytest

from sygen_bot.rag.chunker import SmartChunker
from sygen_bot.rag.indexer import MultiSourceIndexer


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "README.md").write_text("# Project\n\nThis is a test project.\n")
    (ws / "notes.txt").write_text("Important note about deployment.\n")
    (ws / "config.yaml").write_text("key: value\nother: data\n")
    (ws / "ignore.pyc").write_text("bytecode")
    return ws


@pytest.fixture
def indexer(workspace: Path) -> MultiSourceIndexer:
    chunker = SmartChunker(chunk_size=200, overlap=0, min_chunk_size=10)
    return MultiSourceIndexer(
        chunker=chunker,
        workspace_dir=workspace,
        include_patterns=["*.md", "*.txt", "*.yaml"],
        exclude_patterns=["*.pyc"],
    )


class TestMultiSourceIndexer:
    def test_full_reindex(self, indexer: MultiSourceIndexer) -> None:
        chunks = indexer.full_reindex()
        assert len(chunks) > 0
        assert indexer.indexed_count == len(chunks)

    def test_excludes_patterns(self, indexer: MultiSourceIndexer) -> None:
        chunks = indexer.full_reindex()
        sources = {c.source for c in chunks}
        assert not any("pyc" in s for s in sources)

    def test_needs_reindex_after_change(
        self, indexer: MultiSourceIndexer, workspace: Path,
    ) -> None:
        indexer.full_reindex()
        assert not indexer.needs_reindex()

        # Modify a file — bump mtime explicitly to avoid sub-second resolution issues
        import os
        readme = workspace / "README.md"
        readme.write_text("# Updated\n\nNew content.\n")
        st = readme.stat()
        os.utime(readme, (st.st_atime, st.st_mtime + 2))
        assert indexer.needs_reindex()

    def test_incremental_reindex(
        self, indexer: MultiSourceIndexer, workspace: Path,
    ) -> None:
        indexer.full_reindex()
        original_count = indexer.indexed_count

        # Add a new file
        (workspace / "new.md").write_text("# New\n\nBrand new document.\n")
        chunks = indexer.incremental_reindex()
        assert indexer.indexed_count >= original_count

    def test_deleted_file_removed(
        self, indexer: MultiSourceIndexer, workspace: Path,
    ) -> None:
        indexer.full_reindex()
        (workspace / "notes.txt").unlink()
        chunks = indexer.incremental_reindex()
        sources = {c.source for c in chunks}
        assert not any("notes.txt" in s for s in sources)

    def test_memory_modules(self, indexer: MultiSourceIndexer, tmp_path: Path) -> None:
        modules = tmp_path / "modules"
        modules.mkdir()
        (modules / "user.md").write_text("## Preferences\n\n- Likes Python\n- Uses Linux\n")
        chunks = indexer.index_memory_modules(modules)
        assert len(chunks) > 0
        assert any("memory:" in c.source for c in chunks)

    def test_empty_workspace(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        chunker = SmartChunker()
        indexer = MultiSourceIndexer(chunker=chunker, workspace_dir=empty)
        chunks = indexer.full_reindex()
        assert chunks == []
