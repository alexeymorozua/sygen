"""LRU cache for RAG retrieval results.

Avoids redundant search/rerank for repeated or similar queries
within a short time window.
"""

from __future__ import annotations

import time
import threading
from collections import OrderedDict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sygen_bot.rag.chunker import Chunk


class RAGCache:
    """Thread-safe LRU cache with TTL for retrieval results.

    Args:
        max_size: Maximum number of cached queries.
        ttl_seconds: Time-to-live for cache entries (0 = no expiry).
    """

    def __init__(self, max_size: int = 128, ttl_seconds: int = 300) -> None:
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._cache: OrderedDict[str, tuple[list[tuple[Chunk, float]], float]] = (
            OrderedDict()
        )
        self._lock = threading.Lock()

    def get(self, query: str) -> list[tuple[Chunk, float]] | None:
        """Get cached results for a query. Returns None on miss."""
        key = query.strip().lower()
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            results, timestamp = entry
            if self._ttl > 0 and (time.monotonic() - timestamp) > self._ttl:
                del self._cache[key]
                return None
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return results

    def put(self, query: str, results: list[tuple[Chunk, float]]) -> None:
        """Store results for a query."""
        key = query.strip().lower()
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (results, time.monotonic())
            # Evict oldest if over capacity
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def invalidate(self) -> None:
        """Clear the entire cache (e.g., after reindexing)."""
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)
