"""Hybrid retriever: BM25 + Vector search with Reciprocal Rank Fusion.

Combines keyword-based (BM25) and semantic (vector) search results
using RRF to get the best of both worlds — exact keyword matches
and semantic understanding.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sygen_bot.rag.chunker import Chunk

logger = logging.getLogger(__name__)

# RRF constant (standard value from the original paper)
_RRF_K = 60


def reciprocal_rank_fusion(
    *ranked_lists: list[tuple[Chunk, float]],
    weights: list[float] | None = None,
    k: int = _RRF_K,
) -> list[tuple[Chunk, float]]:
    """Fuse multiple ranked lists using Reciprocal Rank Fusion.

    For each result in each list, its RRF score contribution is:
        weight / (k + rank)

    where rank is 1-based position in the list.

    Args:
        *ranked_lists: Variable number of (chunk, score) lists, each sorted by relevance.
        weights: Weight for each list. Default: equal weights.
        k: RRF constant (default 60, from the original paper).

    Returns:
        Merged list of (chunk, rrf_score) sorted by fused score descending.
    """
    if not ranked_lists:
        return []

    n = len(ranked_lists)
    if weights is None:
        weights = [1.0] * n
    elif len(weights) != n:
        weights = [1.0] * n

    # Aggregate scores by chunk_id to handle deduplication
    scores: dict[str, float] = {}
    chunk_map: dict[str, Chunk] = {}

    for list_idx, ranked_list in enumerate(ranked_lists):
        w = weights[list_idx]
        for rank, (chunk, _score) in enumerate(ranked_list, start=1):
            cid = chunk.chunk_id
            if cid not in chunk_map:
                chunk_map[cid] = chunk
            scores[cid] = scores.get(cid, 0.0) + w / (k + rank)

    # Sort by fused score
    result = [
        (chunk_map[cid], score)
        for cid, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)
    ]
    return result


class HybridRetriever:
    """Combines BM25 and vector search with RRF fusion.

    Usage:
        retriever = HybridRetriever(bm25_weight=0.4, vector_weight=0.6)
        retriever.index(chunks)
        results = retriever.search(query, vector_store, top_k=20)
    """

    def __init__(
        self,
        bm25_weight: float = 0.4,
        vector_weight: float = 0.6,
        top_k_retrieval: int = 20,
    ) -> None:
        from sygen_bot.rag.bm25 import BM25Index

        self._bm25 = BM25Index()
        self._bm25_weight = bm25_weight
        self._vector_weight = vector_weight
        self._top_k = top_k_retrieval

    @property
    def bm25(self):  # noqa: ANN201
        """Access the underlying BM25 index."""
        return self._bm25

    def index(self, chunks: list[Chunk]) -> None:
        """Build BM25 index from chunks.

        Vector index is managed separately via ChromaDB.
        """
        self._bm25.build(chunks)

    def search(
        self,
        query: str,
        vector_results: list[tuple[Chunk, float]] | None = None,
        top_k: int | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Hybrid search combining BM25 and vector results.

        Args:
            query: Search query string.
            vector_results: Pre-computed vector search results as (chunk, score) list.
                If None, only BM25 results are used.
            top_k: Number of results to return. Default: self._top_k.

        Returns:
            Fused (chunk, rrf_score) list sorted by relevance.
        """
        k = top_k or self._top_k

        bm25_results = self._bm25.search(query, top_k=k * 2)

        lists_to_fuse: list[list[tuple[Chunk, float]]] = []
        weights: list[float] = []

        if bm25_results:
            lists_to_fuse.append(bm25_results)
            weights.append(self._bm25_weight)

        if vector_results:
            lists_to_fuse.append(vector_results)
            weights.append(self._vector_weight)

        if not lists_to_fuse:
            return []

        fused = reciprocal_rank_fusion(*lists_to_fuse, weights=weights)
        return fused[:k]
