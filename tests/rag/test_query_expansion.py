"""Tests for query expansion."""

from __future__ import annotations

from sygen_bot.rag.query_expansion import expand_query


class TestQueryExpansion:
    def test_original_always_first(self) -> None:
        result = expand_query("test query", max_variants=3)
        assert result[0] == "test query"

    def test_short_query_no_expansion(self) -> None:
        result = expand_query("hi", max_variants=5)
        assert len(result) == 1

    def test_max_variants_respected(self) -> None:
        result = expand_query(
            "Python programming language for web development",
            max_variants=2,
        )
        assert len(result) <= 2

    def test_stopwords_removed(self) -> None:
        result = expand_query(
            "what is the best programming language for web development",
            max_variants=3,
        )
        assert len(result) >= 2
        # Second variant should be keywords only (no stopwords)
        if len(result) > 1:
            keywords = result[1]
            assert "the" not in keywords.split()
            assert "is" not in keywords.split()

    def test_russian_stopwords(self) -> None:
        result = expand_query(
            "что это за язык программирования для веб разработки",
            max_variants=3,
        )
        if len(result) > 1:
            assert "что" not in result[1].split()
            assert "это" not in result[1].split()

    def test_single_variant(self) -> None:
        result = expand_query("anything", max_variants=1)
        assert len(result) == 1
        assert result[0] == "anything"

    def test_deduplication(self) -> None:
        result = expand_query("Python", max_variants=5)
        # All variants should be unique
        assert len(result) == len(set(result))
