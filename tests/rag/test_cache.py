"""Tests for RAG cache."""

from __future__ import annotations

import time
from unittest.mock import patch

from sygen_bot.rag.cache import RAGCache
from sygen_bot.rag.chunker import Chunk


def _chunk(text: str) -> Chunk:
    return Chunk(text=text, chunk_id="c1", source="test.md")


class TestRAGCache:
    def test_put_and_get(self) -> None:
        cache = RAGCache(max_size=10, ttl_seconds=60)
        results = [(_chunk("hello"), 0.9)]
        cache.put("test query", results)
        assert cache.get("test query") == results

    def test_miss(self) -> None:
        cache = RAGCache()
        assert cache.get("nonexistent") is None

    def test_case_insensitive(self) -> None:
        cache = RAGCache()
        results = [(_chunk("hello"), 0.9)]
        cache.put("Test Query", results)
        assert cache.get("test query") == results

    def test_ttl_expiry(self) -> None:
        cache = RAGCache(ttl_seconds=1)
        results = [(_chunk("hello"), 0.9)]
        cache.put("query", results)
        assert cache.get("query") is not None
        # Simulate time passing
        with patch("sygen_bot.rag.cache.time") as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 2
            assert cache.get("query") is None

    def test_lru_eviction(self) -> None:
        cache = RAGCache(max_size=2, ttl_seconds=0)
        cache.put("a", [(_chunk("a"), 1.0)])
        cache.put("b", [(_chunk("b"), 1.0)])
        cache.put("c", [(_chunk("c"), 1.0)])
        # "a" should be evicted
        assert cache.get("a") is None
        assert cache.get("b") is not None
        assert cache.get("c") is not None

    def test_invalidate(self) -> None:
        cache = RAGCache()
        cache.put("a", [(_chunk("a"), 1.0)])
        cache.put("b", [(_chunk("b"), 1.0)])
        assert cache.size == 2
        cache.invalidate()
        assert cache.size == 0

    def test_size(self) -> None:
        cache = RAGCache()
        assert cache.size == 0
        cache.put("a", [])
        assert cache.size == 1
