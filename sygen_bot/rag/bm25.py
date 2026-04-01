"""BM25 keyword search index over document chunks.

Uses ``rank_bm25`` (pure Python, no external deps beyond pip).
Falls back gracefully when the package is not installed.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sygen_bot.rag.chunker import Chunk

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    """Simple unicode-aware tokenizer. Works for any language."""
    return [w.lower() for w in _WORD_RE.findall(text)]


def is_available() -> bool:
    """Check if rank_bm25 is importable."""
    try:
        import rank_bm25 as _  # noqa: F401
        return True
    except ImportError:
        return False


class BM25Index:
    """BM25 index over a list of Chunk objects.

    Builds an inverted index for fast keyword retrieval.
    Complements vector search by catching exact keyword matches
    that embedding models might miss.
    """

    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._bm25: object | None = None  # BM25Okapi instance
        self._corpus: list[list[str]] = []

    @property
    def count(self) -> int:
        return len(self._chunks)

    def build(self, chunks: list[Chunk]) -> None:
        """Build the BM25 index from a list of chunks."""
        if not chunks:
            self._chunks = []
            self._bm25 = None
            self._corpus = []
            return

        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            logger.warning("rank_bm25 not installed — BM25 search disabled")
            return

        self._chunks = list(chunks)
        self._corpus = [_tokenize(c.text) for c in chunks]
        self._bm25 = BM25Okapi(self._corpus)
        logger.info("BM25 index built: %d chunks", len(chunks))

    def search(self, query: str, top_k: int = 20) -> list[tuple[Chunk, float]]:
        """Search for chunks matching the query.

        Returns list of (chunk, score) tuples sorted by score descending.
        """
        if self._bm25 is None or not self._chunks:
            return []

        tokens = _tokenize(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)  # type: ignore[union-attr]

        # Pair chunks with scores, filter zero scores
        scored = [
            (self._chunks[i], float(scores[i]))
            for i in range(len(self._chunks))
            if scores[i] > 0
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def add_chunks(self, new_chunks: list[Chunk]) -> None:
        """Incrementally add chunks and rebuild the index."""
        self._chunks.extend(new_chunks)
        self.build(self._chunks)
