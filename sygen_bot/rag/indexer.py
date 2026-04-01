"""Multi-source document indexer for the RAG pipeline.

Indexes content from multiple sources:
1. Memory modules (markdown facts)
2. Workspace files (markdown, YAML, text)
3. Workflow definitions
4. Skill descriptions

Watches for file changes and triggers reindexing.
"""

from __future__ import annotations

import fnmatch
import hashlib
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sygen_bot.rag.chunker import Chunk, SmartChunker

logger = logging.getLogger(__name__)


class DocumentSource:
    """Represents an indexable document source."""

    __slots__ = ("path", "source_type", "mtime")

    def __init__(self, path: Path, source_type: str, mtime: float) -> None:
        self.path = path
        self.source_type = source_type
        self.mtime = mtime


class MultiSourceIndexer:
    """Indexes and chunks documents from multiple workspace sources.

    Tracks file modification times to enable incremental reindexing.

    Args:
        chunker: SmartChunker instance for splitting documents.
        workspace_dir: Root workspace directory.
        include_patterns: Glob patterns for files to index.
        exclude_patterns: Glob patterns for files to exclude.
    """

    def __init__(
        self,
        chunker: SmartChunker,
        workspace_dir: Path,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        self._chunker = chunker
        self._workspace_dir = workspace_dir
        self._include = include_patterns or ["*.md", "*.yaml", "*.yml", "*.txt"]
        self._exclude = exclude_patterns or [
            "vector_db/**", "__pycache__/**", "*.pyc",
        ]
        self._indexed_mtimes: dict[str, float] = {}  # path -> mtime at last index
        self._all_chunks: list[Chunk] = []
        self._content_hashes: dict[str, str] = {}  # path -> content hash

    @property
    def chunks(self) -> list[Chunk]:
        return list(self._all_chunks)

    @property
    def indexed_count(self) -> int:
        return len(self._all_chunks)

    def needs_reindex(self) -> bool:
        """Check if any source files have changed since last index."""
        sources = self._discover_sources()
        current_paths: set[str] = set()
        for src in sources:
            key = str(src.path)
            current_paths.add(key)
            old_mtime = self._indexed_mtimes.get(key, 0.0)
            if src.mtime > old_mtime:
                return True
        # Check for deleted files
        if set(self._indexed_mtimes.keys()) != current_paths:
            return True
        return False

    def full_reindex(self) -> list[Chunk]:
        """Perform a full reindex of all sources.

        Returns the complete list of chunks.
        """
        start = time.monotonic()
        sources = self._discover_sources()

        self._all_chunks = []
        self._indexed_mtimes = {}
        self._content_hashes = {}

        for src in sources:
            chunks = self._index_source(src)
            self._all_chunks.extend(chunks)

        elapsed = time.monotonic() - start
        logger.info(
            "Full reindex: %d chunks from %d sources (%.2fs)",
            len(self._all_chunks), len(sources), elapsed,
        )
        return self._all_chunks

    def incremental_reindex(self) -> list[Chunk]:
        """Reindex only changed files. Returns the updated full chunk list."""
        sources = self._discover_sources()
        current_paths = {str(s.path) for s in sources}

        # Remove chunks from deleted files
        deleted = set(self._indexed_mtimes.keys()) - current_paths
        if deleted:
            self._all_chunks = [
                c for c in self._all_chunks if c.source not in deleted
            ]
            for d in deleted:
                self._indexed_mtimes.pop(d, None)
                self._content_hashes.pop(d, None)

        # Reindex changed files
        changed = 0
        for src in sources:
            key = str(src.path)
            old_mtime = self._indexed_mtimes.get(key, 0.0)
            if src.mtime <= old_mtime:
                continue

            # Check content hash to avoid reindexing if content unchanged
            try:
                content = src.path.read_text(encoding="utf-8")
            except OSError:
                continue
            content_hash = hashlib.md5(content.encode()).hexdigest()
            if content_hash == self._content_hashes.get(key):
                self._indexed_mtimes[key] = src.mtime
                continue

            # Remove old chunks for this file
            self._all_chunks = [
                c for c in self._all_chunks if c.source != key
            ]

            # Add new chunks
            chunks = self._chunker.chunk_text(content, source=key)
            self._all_chunks.extend(chunks)
            self._indexed_mtimes[key] = src.mtime
            self._content_hashes[key] = content_hash
            changed += 1

        if changed:
            logger.info("Incremental reindex: %d files changed, %d total chunks",
                        changed, len(self._all_chunks))
        return self._all_chunks

    def index_memory_modules(self, modules_dir: Path) -> list[Chunk]:
        """Index memory module files specifically.

        Memory modules are markdown files with structured facts.
        """
        chunks: list[Chunk] = []
        if not modules_dir.is_dir():
            return chunks

        for md_file in sorted(modules_dir.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
            except OSError:
                continue
            if not content.strip():
                continue
            file_chunks = self._chunker.chunk_text(
                content, source=f"memory:{md_file.name}",
            )
            chunks.extend(file_chunks)
        return chunks

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _discover_sources(self) -> list[DocumentSource]:
        """Find all indexable files in the workspace."""
        sources: list[DocumentSource] = []
        if not self._workspace_dir.is_dir():
            return sources

        for pattern in self._include:
            for path in self._workspace_dir.rglob(pattern):
                if not path.is_file():
                    continue
                rel = str(path.relative_to(self._workspace_dir))
                if self._is_excluded(rel):
                    continue
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                sources.append(DocumentSource(path, pattern, mtime))

        return sources

    def _is_excluded(self, rel_path: str) -> bool:
        """Check if a relative path matches any exclude pattern."""
        for pattern in self._exclude:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
        return False

    def _index_source(self, src: DocumentSource) -> list[Chunk]:
        """Index a single source file."""
        try:
            content = src.path.read_text(encoding="utf-8")
        except OSError:
            return []

        if not content.strip():
            return []

        key = str(src.path)
        self._indexed_mtimes[key] = src.mtime
        self._content_hashes[key] = hashlib.md5(content.encode()).hexdigest()

        return self._chunker.chunk_text(content, source=key)
