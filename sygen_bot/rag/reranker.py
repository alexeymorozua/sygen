"""ColBERT v2 multilingual reranker.

Uses ``colbert-xm`` for token-level late-interaction reranking.
Falls back to cross-encoder if ColBERT is not available,
and to no-op if neither is installed.

All models are free, local, and require no API keys.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sygen_bot.rag.chunker import Chunk

logger = logging.getLogger(__name__)

# Model priorities (tried in order)
_COLBERT_MODEL = "antoinelouis/colbert-xm"
_CROSS_ENCODER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


def _resolve_device():  # noqa: ANN201
    """Detect best available device (GPU > CPU)."""
    import torch

    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _try_load_colbert(model_name: str):  # noqa: ANN201
    """Try to load a ColBERT model. Returns (model, tokenizer, device) or None."""
    try:
        from transformers import AutoModel, AutoTokenizer

        device = _resolve_device()
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name)
        model.eval()
        model.to(device)
        logger.info("ColBERT reranker loaded: %s (device=%s)", model_name, device)
        return model, tokenizer, device
    except (ImportError, OSError) as exc:
        logger.debug("ColBERT not available (%s): %s", model_name, exc)
        return None


def _try_load_cross_encoder(model_name: str):  # noqa: ANN201
    """Try to load a cross-encoder model. Returns model or None."""
    try:
        from sentence_transformers import CrossEncoder

        model = CrossEncoder(model_name)
        logger.info("Cross-encoder reranker loaded: %s", model_name)
        return model
    except (ImportError, OSError) as exc:
        logger.debug("Cross-encoder not available (%s): %s", model_name, exc)
        return None


class ColBERTReranker:
    """Multilingual reranker using ColBERT v2 late interaction.

    Late interaction means:
    1. Query and document tokens are encoded independently
    2. Relevance is computed via MaxSim (max similarity per query token)
    3. Document embeddings can be pre-computed for speed

    Falls back to cross-encoder, then to no-op passthrough.
    """

    def __init__(self, model_name: str = _COLBERT_MODEL) -> None:
        self._model = None
        self._tokenizer = None
        self._device = None
        self._cross_encoder = None
        self._mode: str = "none"  # "colbert", "cross_encoder", "none"
        self._model_name = model_name

    def load(self) -> str:
        """Load the reranker model. Returns the mode name.

        Tries ColBERT first, then cross-encoder, then no-op.
        """
        # Try ColBERT
        result = _try_load_colbert(self._model_name)
        if result is not None:
            self._model, self._tokenizer, self._device = result
            self._mode = "colbert"
            return self._mode

        # Try cross-encoder fallback
        self._cross_encoder = _try_load_cross_encoder(_CROSS_ENCODER_MODEL)
        if self._cross_encoder is not None:
            self._mode = "cross_encoder"
            return self._mode

        logger.warning("No reranker available — using passthrough")
        self._mode = "none"
        return self._mode

    @property
    def mode(self) -> str:
        return self._mode

    def rerank(
        self,
        query: str,
        chunks: list[tuple[Chunk, float]],
        top_k: int = 5,
    ) -> list[tuple[Chunk, float]]:
        """Rerank chunks by relevance to query.

        Args:
            query: The user query.
            chunks: List of (chunk, retrieval_score) from hybrid search.
            top_k: Number of top results to return.

        Returns:
            Reranked list of (chunk, rerank_score).
        """
        if not chunks:
            return []

        if self._mode == "none":
            return chunks[:top_k]

        if self._mode == "colbert":
            return self._rerank_colbert(query, chunks, top_k)

        return self._rerank_cross_encoder(query, chunks, top_k)

    def _rerank_colbert(
        self,
        query: str,
        chunks: list[tuple[Chunk, float]],
        top_k: int,
    ) -> list[tuple[Chunk, float]]:
        """Rerank using batched ColBERT MaxSim late interaction."""
        import torch

        model = self._model
        tokenizer = self._tokenizer
        device = self._device

        # Encode query once
        q_enc = tokenizer(
            query,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=128,
        )
        q_enc = {k: v.to(device) for k, v in q_enc.items()}
        with torch.no_grad():
            q_emb = model(**q_enc).last_hidden_state  # (1, q_len, dim)

        # Batch-encode all documents at once
        doc_texts = [chunk.text for chunk, _ in chunks]
        d_enc = tokenizer(
            doc_texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        )
        d_enc = {k: v.to(device) for k, v in d_enc.items()}
        with torch.no_grad():
            d_emb = model(**d_enc).last_hidden_state  # (batch, d_len, dim)

        # Compute MaxSim for each document in the batch
        # q_emb: (1, q_len, dim) -> expand to (batch, q_len, dim)
        q_expanded = q_emb.expand(d_emb.size(0), -1, -1)

        # Similarity: (batch, q_len, d_len)
        sim = torch.bmm(q_expanded, d_emb.transpose(1, 2))

        # MaxSim: max over doc tokens for each query token, then sum
        max_sim = sim.max(dim=2).values  # (batch, q_len)

        # Mask padding tokens in the query (attention_mask from q_enc)
        q_mask = q_enc["attention_mask"].expand(d_emb.size(0), -1).float()
        scores = (max_sim * q_mask).sum(dim=1)  # (batch,)

        scored: list[tuple[Chunk, float]] = [
            (chunks[i][0], float(scores[i]))
            for i in range(len(chunks))
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def _rerank_cross_encoder(
        self,
        query: str,
        chunks: list[tuple[Chunk, float]],
        top_k: int,
    ) -> list[tuple[Chunk, float]]:
        """Rerank using cross-encoder scoring."""
        pairs = [(query, chunk.text) for chunk, _ in chunks]
        scores = self._cross_encoder.predict(pairs)  # type: ignore[union-attr]

        scored = [
            (chunks[i][0], float(scores[i]))
            for i in range(len(chunks))
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
