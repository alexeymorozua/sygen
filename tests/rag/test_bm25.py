"""Tests for BM25 index."""

from __future__ import annotations

import pytest

from sygen_bot.rag.bm25 import BM25Index, _tokenize, is_available
from sygen_bot.rag.chunker import Chunk, SmartChunker


class TestTokenize:
    def test_basic(self) -> None:
        assert _tokenize("Hello World") == ["hello", "world"]

    def test_unicode(self) -> None:
        tokens = _tokenize("Привет мир")
        assert "привет" in tokens
        assert "мир" in tokens

    def test_empty(self) -> None:
        assert _tokenize("") == []

    def test_special_chars(self) -> None:
        tokens = _tokenize("hello-world_test.py")
        assert "hello" in tokens
        assert "world_test" in tokens


@pytest.mark.skipif(not is_available(), reason="rank_bm25 not installed")
class TestBM25Index:
    @pytest.fixture
    def chunks(self) -> list[Chunk]:
        texts = [
            "Python is a programming language",
            "JavaScript runs in the browser",
            "Rust is a systems programming language",
            "Python has great libraries for data science",
            "Docker containers for deployment",
        ]
        return [
            Chunk(text=t, chunk_id=f"c{i}", source="test.md")
            for i, t in enumerate(texts)
        ]

    def test_build_and_count(self, chunks: list[Chunk]) -> None:
        idx = BM25Index()
        idx.build(chunks)
        assert idx.count == 5

    def test_search_relevant(self, chunks: list[Chunk]) -> None:
        idx = BM25Index()
        idx.build(chunks)
        results = idx.search("Python programming", top_k=3)
        assert len(results) > 0
        # Top result should mention Python
        assert "Python" in results[0][0].text

    def test_search_returns_scores(self, chunks: list[Chunk]) -> None:
        idx = BM25Index()
        idx.build(chunks)
        results = idx.search("programming language")
        for chunk, score in results:
            assert isinstance(score, float)
            assert score > 0

    def test_search_empty_query(self, chunks: list[Chunk]) -> None:
        idx = BM25Index()
        idx.build(chunks)
        assert idx.search("") == []

    def test_search_no_index(self) -> None:
        idx = BM25Index()
        assert idx.search("test") == []

    def test_empty_build(self) -> None:
        idx = BM25Index()
        idx.build([])
        assert idx.count == 0
        assert idx.search("test") == []
