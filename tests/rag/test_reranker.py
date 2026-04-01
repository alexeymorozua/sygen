"""Tests for ColBERT/cross-encoder reranker with mocked models."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sygen_bot.rag.chunker import Chunk
from sygen_bot.rag.reranker import ColBERTReranker


def _make_chunk(text: str, cid: str) -> Chunk:
    return Chunk(text=text, chunk_id=cid, source="test.md")


@pytest.fixture
def chunks() -> list[tuple[Chunk, float]]:
    return [
        (_make_chunk("Python is a programming language", "c1"), 0.9),
        (_make_chunk("JavaScript runs in browsers", "c2"), 0.7),
        (_make_chunk("Rust is fast and safe", "c3"), 0.5),
    ]


class TestColBERTRerankerNoModels:
    """Tests that work without any ML libraries installed."""

    def test_default_mode_is_none(self) -> None:
        reranker = ColBERTReranker()
        assert reranker.mode == "none"

    def test_passthrough_when_no_models(
        self, chunks: list[tuple[Chunk, float]],
    ) -> None:
        reranker = ColBERTReranker()
        # mode is "none" by default — passthrough
        result = reranker.rerank("test query", chunks, top_k=2)
        assert len(result) == 2
        assert result[0][0].chunk_id == "c1"  # original order preserved

    def test_rerank_empty_chunks(self) -> None:
        reranker = ColBERTReranker()
        assert reranker.rerank("query", [], top_k=5) == []

    def test_top_k_respected(self, chunks: list[tuple[Chunk, float]]) -> None:
        reranker = ColBERTReranker()
        result = reranker.rerank("query", chunks, top_k=1)
        assert len(result) == 1


class TestColBERTRerankerMocked:
    """Tests with mocked transformer models."""

    def test_load_colbert_success(self) -> None:
        mock_model = MagicMock()
        mock_tokenizer = MagicMock()
        mock_device = MagicMock()

        with patch(
            "sygen_bot.rag.reranker._try_load_colbert",
            return_value=(mock_model, mock_tokenizer, mock_device),
        ):
            reranker = ColBERTReranker()
            mode = reranker.load()
            assert mode == "colbert"
            assert reranker.mode == "colbert"

    def test_load_falls_back_to_cross_encoder(self) -> None:
        mock_ce = MagicMock()

        with patch("sygen_bot.rag.reranker._try_load_colbert", return_value=None), \
             patch("sygen_bot.rag.reranker._try_load_cross_encoder", return_value=mock_ce):
            reranker = ColBERTReranker()
            mode = reranker.load()
            assert mode == "cross_encoder"

    def test_load_falls_back_to_none(self) -> None:
        with patch("sygen_bot.rag.reranker._try_load_colbert", return_value=None), \
             patch("sygen_bot.rag.reranker._try_load_cross_encoder", return_value=None):
            reranker = ColBERTReranker()
            mode = reranker.load()
            assert mode == "none"

    def test_cross_encoder_rerank(
        self, chunks: list[tuple[Chunk, float]],
    ) -> None:
        mock_ce = MagicMock()
        # Cross-encoder returns scores: c3 > c1 > c2
        mock_ce.predict.return_value = [0.3, 0.1, 0.9]

        with patch("sygen_bot.rag.reranker._try_load_colbert", return_value=None), \
             patch("sygen_bot.rag.reranker._try_load_cross_encoder", return_value=mock_ce):
            reranker = ColBERTReranker()
            reranker.load()

        result = reranker.rerank("fast language", chunks, top_k=2)
        assert len(result) == 2
        # c3 ("Rust is fast") should be first (score 0.9)
        assert result[0][0].chunk_id == "c3"
        # Verify predict was called with correct pairs
        mock_ce.predict.assert_called_once()
        pairs = mock_ce.predict.call_args[0][0]
        assert len(pairs) == 3
        assert pairs[0] == ("fast language", "Python is a programming language")

    def test_colbert_rerank_with_mock_tensors(
        self, chunks: list[tuple[Chunk, float]],
    ) -> None:
        """Test ColBERT reranking with mocked torch tensors."""
        try:
            import torch
        except ImportError:
            pytest.skip("torch not installed")

        device = torch.device("cpu")

        # Create mock model that returns real tensors
        mock_model = MagicMock()
        mock_tokenizer = MagicMock()

        # Query encoding: (1, 4, 8) — 4 query tokens, dim 8
        q_output = MagicMock()
        q_output.last_hidden_state = torch.randn(1, 4, 8)

        # Doc encoding: (3, 6, 8) — 3 docs, 6 doc tokens, dim 8
        d_output = MagicMock()
        d_output.last_hidden_state = torch.randn(3, 6, 8)

        call_count = [0]

        def mock_forward(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return q_output
            return d_output

        mock_model.side_effect = mock_forward
        mock_model.return_value = q_output  # first call

        # Mock tokenizer to return proper tensors
        def mock_tokenize(*args, **kwargs):
            batch_size = len(args[0]) if isinstance(args[0], list) else 1
            seq_len = 6 if batch_size > 1 else 4
            return {
                "input_ids": torch.ones(batch_size, seq_len, dtype=torch.long),
                "attention_mask": torch.ones(batch_size, seq_len, dtype=torch.long),
            }

        mock_tokenizer.side_effect = mock_tokenize

        # Set up model calls to return different outputs
        mock_model.side_effect = [q_output, d_output]

        reranker = ColBERTReranker()
        reranker._model = mock_model
        reranker._tokenizer = mock_tokenizer
        reranker._device = device
        reranker._mode = "colbert"

        result = reranker.rerank("test query", chunks, top_k=2)
        assert len(result) == 2
        # All results should have float scores
        for chunk, score in result:
            assert isinstance(score, float)
        # Results should be sorted by score descending
        assert result[0][1] >= result[1][1]
