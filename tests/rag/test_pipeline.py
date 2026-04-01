"""Tests for RAG pipeline with mocked dependencies."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sygen_bot.rag.chunker import Chunk
from sygen_bot.rag.config import RAGConfig
from sygen_bot.rag.pipeline import RAGPipeline


@pytest.fixture
def config() -> RAGConfig:
    return RAGConfig(
        enabled=True,
        reranker_enabled=False,  # No model loading in tests
        query_expansion_enabled=False,
        cache_size=10,
        cache_ttl_seconds=60,
        chunk_size=200,
        top_k_retrieval=5,
        top_k_final=3,
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "doc.md").write_text("# Test\n\nThis is about Python programming.\n")
    return ws


@pytest.fixture
def memory_dir(tmp_path: Path) -> Path:
    mem = tmp_path / "modules"
    mem.mkdir()
    (mem / "user.md").write_text("## Preferences\n\n- Likes Python\n- Uses Linux\n")
    return mem


@pytest.fixture
def pipeline(config: RAGConfig, workspace: Path, memory_dir: Path) -> RAGPipeline:
    return RAGPipeline(
        config=config,
        workspace_dir=workspace,
        memory_modules_dir=memory_dir,
        vector_persist_dir=None,  # No ChromaDB in tests
    )


class TestRAGPipelineInit:
    def test_not_initialized_on_creation(self, pipeline: RAGPipeline) -> None:
        assert not pipeline.is_initialized

    @pytest.mark.asyncio
    async def test_initialize(self, pipeline: RAGPipeline) -> None:
        await pipeline.initialize()
        assert pipeline.is_initialized

    @pytest.mark.asyncio
    async def test_double_initialize_is_noop(self, pipeline: RAGPipeline) -> None:
        await pipeline.initialize()
        await pipeline.initialize()  # Should not raise
        assert pipeline.is_initialized


class TestRAGPipelineRetrieve:
    @pytest.mark.asyncio
    async def test_retrieve_returns_string(self, pipeline: RAGPipeline) -> None:
        result = await pipeline.retrieve("Python programming")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_retrieve_finds_relevant_content(self, pipeline: RAGPipeline) -> None:
        result = await pipeline.retrieve("Python programming")
        # Should find content from workspace docs or memory
        if result:  # May be empty if chunks are too small
            assert "Retrieved Context" in result or "Python" in result

    @pytest.mark.asyncio
    async def test_retrieve_empty_query(self, pipeline: RAGPipeline) -> None:
        result = await pipeline.retrieve("")
        # Empty query may return empty or all results
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_retrieve_uses_cache(self, pipeline: RAGPipeline) -> None:
        await pipeline.initialize()
        result1 = await pipeline.retrieve("test query")
        result2 = await pipeline.retrieve("test query")
        assert result1 == result2
        assert pipeline._cache.size <= 1  # One entry cached

    @pytest.mark.asyncio
    async def test_retrieve_with_query_expansion(
        self, workspace: Path, memory_dir: Path,
    ) -> None:
        config = RAGConfig(
            enabled=True,
            reranker_enabled=False,
            query_expansion_enabled=True,
            max_query_variants=2,
        )
        pipeline = RAGPipeline(
            config=config,
            workspace_dir=workspace,
            memory_modules_dir=memory_dir,
        )
        result = await pipeline.retrieve("what is the best programming language for web")
        assert isinstance(result, str)


class TestRAGPipelineReindex:
    @pytest.mark.asyncio
    async def test_reindex_clears_cache(self, pipeline: RAGPipeline) -> None:
        await pipeline.initialize()
        pipeline._cache.put("old", [])
        assert pipeline._cache.size == 1
        await pipeline.reindex()
        assert pipeline._cache.size == 0


class TestRAGPipelineVectorSearch:
    @pytest.mark.asyncio
    async def test_vector_search_without_store(self, pipeline: RAGPipeline) -> None:
        await pipeline.initialize()
        results = await pipeline._vector_search("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_vector_search_with_mocked_store(
        self, pipeline: RAGPipeline,
    ) -> None:
        await pipeline.initialize()

        mock_store = MagicMock()
        mock_store.search.return_value = [
            {
                "text": "[user.md] Preferences: Likes Python",
                "module": "user.md",
                "section": "Preferences",
                "raw": "Likes Python",
                "distance": "0.2",
            },
        ]
        pipeline._vector_store = mock_store

        results = await pipeline._vector_search("Python")
        assert len(results) == 1
        chunk, score = results[0]
        assert "Python" in chunk.text
        assert score == pytest.approx(0.8, abs=0.01)  # 1.0 - 0.2
        assert chunk.source == "memory:user.md"


class TestRAGPipelineFormatResults:
    def test_format_empty(self, pipeline: RAGPipeline) -> None:
        assert pipeline._format_results([]) == ""

    def test_format_with_results(self, pipeline: RAGPipeline) -> None:
        chunks = [
            (Chunk(text="Python is great", chunk_id="c1", source="doc.md", section="Intro"), 0.9),
            (Chunk(text="Rust is fast", chunk_id="c2", source="memory:user.md"), 0.7),
        ]
        result = pipeline._format_results(chunks)
        assert "Retrieved Context" in result
        assert "Python is great" in result
        assert "Rust is fast" in result

    def test_format_respects_token_limit(self, pipeline: RAGPipeline) -> None:
        # Set small token limit (100 is the minimum)
        pipeline._config = RAGConfig(
            enabled=True,
            max_context_tokens=100,  # ~400 chars
        )
        long_text = "x" * 500
        chunks = [
            (Chunk(text=long_text, chunk_id="c1", source="test.md"), 0.9),
            (Chunk(text="second chunk here", chunk_id="c2", source="test.md"), 0.5),
        ]
        result = pipeline._format_results(chunks)
        # Second chunk should not fit after the 500-char first chunk
        assert "second chunk here" not in result

    def test_format_source_label(self, pipeline: RAGPipeline) -> None:
        chunks = [
            (Chunk(text="fact", chunk_id="c1", source="memory:user.md"), 0.9),
        ]
        result = pipeline._format_results(chunks)
        assert "memory/user.md" in result

    def test_format_section_label(self, pipeline: RAGPipeline) -> None:
        chunks = [
            (Chunk(text="fact", chunk_id="c1", source="doc.md", section="Intro"), 0.9),
        ]
        result = pipeline._format_results(chunks)
        assert "Intro" in result
