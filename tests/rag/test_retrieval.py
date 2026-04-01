"""Tests for hybrid retrieval and RRF fusion."""

from __future__ import annotations

from sygen_bot.rag.chunker import Chunk
from sygen_bot.rag.retrieval import reciprocal_rank_fusion


def _make_chunk(text: str, cid: str) -> Chunk:
    return Chunk(text=text, chunk_id=cid, source="test.md")


class TestRRF:
    def test_empty_lists(self) -> None:
        assert reciprocal_rank_fusion() == []

    def test_single_list(self) -> None:
        c1 = _make_chunk("first", "c1")
        c2 = _make_chunk("second", "c2")
        result = reciprocal_rank_fusion([(c1, 1.0), (c2, 0.5)])
        assert len(result) == 2
        assert result[0][0].chunk_id == "c1"

    def test_fusion_of_two_lists(self) -> None:
        c1 = _make_chunk("doc A", "c1")
        c2 = _make_chunk("doc B", "c2")
        c3 = _make_chunk("doc C", "c3")

        # List 1: c1 > c2
        list1 = [(c1, 1.0), (c2, 0.5)]
        # List 2: c2 > c3
        list2 = [(c2, 1.0), (c3, 0.5)]

        result = reciprocal_rank_fusion(list1, list2)
        # c2 appears in both lists so should have higher RRF score
        ids = [r[0].chunk_id for r in result]
        assert "c2" in ids
        assert "c1" in ids
        assert "c3" in ids
        # c2 should be first (appears in both)
        assert ids[0] == "c2"

    def test_deduplication(self) -> None:
        c1 = _make_chunk("same doc", "c1")
        list1 = [(c1, 1.0)]
        list2 = [(c1, 0.8)]
        result = reciprocal_rank_fusion(list1, list2)
        assert len(result) == 1

    def test_weights(self) -> None:
        c1 = _make_chunk("doc A", "c1")
        c2 = _make_chunk("doc B", "c2")

        list1 = [(c1, 1.0)]  # c1 is first in list1
        list2 = [(c2, 1.0)]  # c2 is first in list2

        # With equal weights, both at rank 1 should have same score
        result_equal = reciprocal_rank_fusion(list1, list2, weights=[1.0, 1.0])
        scores = {r[0].chunk_id: r[1] for r in result_equal}
        assert abs(scores["c1"] - scores["c2"]) < 1e-6

        # With unequal weights, higher-weighted list's top result wins
        result_weighted = reciprocal_rank_fusion(list1, list2, weights=[2.0, 1.0])
        assert result_weighted[0][0].chunk_id == "c1"
