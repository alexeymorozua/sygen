"""Main RAG pipeline — orchestrates all retrieval components.

Usage:
    pipeline = RAGPipeline(config, workspace_dir, memory_modules_dir)
    await pipeline.initialize()
    context = await pipeline.retrieve(query)
    # context is a formatted string ready for prompt injection
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path

from sygen_bot.rag.cache import RAGCache
from sygen_bot.rag.chunker import Chunk, SmartChunker
from sygen_bot.rag.config import RAGConfig
from sygen_bot.rag.indexer import MultiSourceIndexer
from sygen_bot.rag.query_expansion import expand_query
from sygen_bot.rag.reranker import ColBERTReranker
from sygen_bot.rag.retrieval import HybridRetriever

logger = logging.getLogger(__name__)


class RAGPipeline:
    """End-to-end RAG pipeline.

    Combines:
    - Smart chunking (semantic boundaries)
    - BM25 + Vector hybrid search with RRF fusion
    - ColBERT v2 multilingual reranking
    - Query expansion
    - LRU result cache
    - Multi-source workspace indexing

    All components are free, local, and require no API keys.
    """

    def __init__(
        self,
        config: RAGConfig,
        workspace_dir: Path | None = None,
        memory_modules_dir: Path | None = None,
        vector_persist_dir: Path | None = None,
        embedding_model: str = "",
    ) -> None:
        self._config = config
        self._workspace_dir = workspace_dir
        self._memory_modules_dir = memory_modules_dir
        self._vector_persist_dir = vector_persist_dir
        self._embedding_model = embedding_model or config.embedding_model

        # Components (initialized lazily)
        self._chunker = SmartChunker(
            chunk_size=config.chunk_size,
            overlap=config.chunk_overlap,
            min_chunk_size=config.min_chunk_size,
        )
        self._retriever = HybridRetriever(
            bm25_weight=config.bm25_weight,
            vector_weight=config.vector_weight,
            top_k_retrieval=config.top_k_retrieval,
        )
        self._reranker: ColBERTReranker | None = None
        self._cache = RAGCache(
            max_size=config.cache_size,
            ttl_seconds=config.cache_ttl_seconds,
        )
        self._indexer: MultiSourceIndexer | None = None
        self._initialized = False
        self._vector_store = None  # VectorMemoryStore instance

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def initialize(self) -> None:
        """Initialize all RAG components.

        Heavy operations (model loading, indexing) run in thread pool.
        """
        if self._initialized:
            return

        # 1. Set up indexer
        if self._workspace_dir and self._config.index_workspace:
            self._indexer = MultiSourceIndexer(
                chunker=self._chunker,
                workspace_dir=self._workspace_dir,
                include_patterns=self._config.workspace_glob_patterns,
                exclude_patterns=self._config.workspace_exclude_patterns,
            )

        # 2. Build initial index (in thread pool)
        await asyncio.to_thread(self._build_index)

        # 3. Load reranker (in thread pool, can be slow)
        if self._config.reranker_enabled:
            self._reranker = ColBERTReranker(model_name=self._config.reranker_model)
            mode = await asyncio.to_thread(self._reranker.load)
            logger.info("Reranker mode: %s", mode)

        # 4. Initialize vector store
        if self._vector_persist_dir:
            await asyncio.to_thread(self._init_vector_store)

        self._initialized = True
        logger.info("RAG pipeline initialized")

    def _build_index(self) -> None:
        """Build BM25 index from all sources (runs in thread)."""
        all_chunks: list[Chunk] = []

        # Index workspace files
        if self._indexer:
            workspace_chunks = self._indexer.full_reindex()
            all_chunks.extend(workspace_chunks)

        # Index memory modules
        if self._memory_modules_dir and self._config.index_memory:
            memory_chunks = self._chunker.chunk_text(
                self._read_memory_modules(), source="memory",
            )
            all_chunks.extend(memory_chunks)

        self._retriever.index(all_chunks)
        logger.info("BM25 index built: %d chunks", len(all_chunks))

    def _init_vector_store(self) -> None:
        """Initialize ChromaDB vector store (runs in thread)."""
        from sygen_bot.memory.vector import get_store

        store = get_store(
            self._vector_persist_dir,  # type: ignore[arg-type]
            model_name=self._embedding_model or None,
        )
        if store is not None:
            self._vector_store = store
            # Ensure indexed
            if self._memory_modules_dir and store.needs_reindex(self._memory_modules_dir):
                store.reindex_modules(self._memory_modules_dir)

    def _read_memory_modules(self) -> str:
        """Read all memory modules into a single text."""
        if not self._memory_modules_dir or not self._memory_modules_dir.is_dir():
            return ""
        parts: list[str] = []
        for md_file in sorted(self._memory_modules_dir.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
                if content.strip():
                    parts.append(f"## {md_file.stem}\n\n{content}")
            except OSError:
                continue
        return "\n\n".join(parts)

    async def retrieve(self, query: str) -> str:
        """Run the full retrieval pipeline and return formatted context.

        Steps:
        1. Check cache
        2. Expand query
        3. Hybrid search (BM25 + Vector)
        4. Rerank with ColBERT
        5. Format and return

        Args:
            query: User's message / query string.

        Returns:
            Formatted context string ready for prompt injection.
            Empty string if no relevant results.
        """
        if not self._initialized:
            await self.initialize()

        # 1. Check cache
        cached = self._cache.get(query)
        if cached is not None:
            return self._format_results(cached)

        # 2. Query expansion
        queries = [query]
        if self._config.query_expansion_enabled:
            queries = expand_query(query, max_variants=self._config.max_query_variants)

        # 3. Hybrid search for each query variant
        all_results: list[tuple[Chunk, float]] = []
        for q in queries:
            # Vector search
            vector_results = await self._vector_search(q)
            # Hybrid (BM25 + vector with RRF)
            hybrid = self._retriever.search(
                q, vector_results=vector_results,
                top_k=self._config.top_k_retrieval,
            )
            all_results.extend(hybrid)

        # Deduplicate by chunk_id, keep highest score
        seen: dict[str, tuple[Chunk, float]] = {}
        for chunk, score in all_results:
            if chunk.chunk_id not in seen or score > seen[chunk.chunk_id][1]:
                seen[chunk.chunk_id] = (chunk, score)
        deduped = sorted(seen.values(), key=lambda x: x[1], reverse=True)
        deduped = deduped[:self._config.top_k_retrieval]

        # 4. Rerank
        if self._reranker and self._config.reranker_enabled and deduped:
            reranked = await asyncio.to_thread(
                self._reranker.rerank, query, deduped, self._config.reranker_top_k,
            )
        else:
            reranked = deduped[:self._config.top_k_final]

        # 5. Cache and format
        self._cache.put(query, reranked)
        return self._format_results(reranked)

    async def _vector_search(self, query: str) -> list[tuple[Chunk, float]]:
        """Run vector search and convert results to Chunk format."""
        if self._vector_store is None:
            return []

        results = await asyncio.to_thread(
            self._vector_store.search, query,
            n_results=self._config.top_k_retrieval,
        )

        # Convert vector results to Chunk objects
        chunks: list[tuple[Chunk, float]] = []
        for fact in results:
            raw = fact.get("raw", fact.get("text", ""))
            cid = hashlib.md5(f"vec:{fact.get('module', '')}:{raw}".encode()).hexdigest()[:12]
            chunk = Chunk(
                text=fact["text"],
                chunk_id=cid,
                source=f"memory:{fact.get('module', '')}",
                section=fact.get("section", ""),
            )
            # ChromaDB returns cosine distance; convert to similarity
            distance = float(fact.get("distance", "0.5"))
            similarity = max(0.0, 1.0 - distance)
            chunks.append((chunk, similarity))
        return chunks

    async def reindex(self) -> None:
        """Trigger a reindex of all sources."""
        self._cache.invalidate()
        await asyncio.to_thread(self._build_index)
        if self._vector_store and self._memory_modules_dir:
            await asyncio.to_thread(
                self._vector_store.reindex_modules, self._memory_modules_dir,
            )

    def _format_results(self, results: list[tuple[Chunk, float]]) -> str:
        """Format retrieval results for prompt injection."""
        if not results:
            return ""

        header = self._config.injection_header
        lines = [header]

        total_chars = 0
        # Rough token-to-char estimate (1 token ≈ 4 chars)
        max_chars = self._config.max_context_tokens * 4

        for chunk, score in results:
            chunk_text = chunk.text.strip()
            if total_chars + len(chunk_text) > max_chars:
                break

            source_label = chunk.source
            if source_label.startswith("memory:"):
                source_label = f"memory/{source_label[7:]}"

            section_part = f" > {chunk.section}" if chunk.section else ""
            lines.append(f"\n**[{source_label}{section_part}]**")
            lines.append(chunk_text)
            total_chars += len(chunk_text)

        return "\n".join(lines) if len(lines) > 1 else ""
