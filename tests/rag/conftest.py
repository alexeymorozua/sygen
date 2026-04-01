"""Shared fixtures for RAG tests."""

from __future__ import annotations

import pytest

from sygen_bot.rag.chunker import Chunk, SmartChunker
from sygen_bot.rag.config import RAGConfig


@pytest.fixture
def chunker() -> SmartChunker:
    return SmartChunker(chunk_size=200, overlap=30, min_chunk_size=20)


@pytest.fixture
def rag_config() -> RAGConfig:
    return RAGConfig(
        enabled=True,
        chunk_size=200,
        chunk_overlap=30,
        reranker_enabled=False,  # Don't load models in tests
    )


@pytest.fixture
def sample_markdown() -> str:
    return (
        "# Introduction\n\n"
        "This is the first paragraph about Python programming.\n\n"
        "Python is a high-level programming language.\n\n"
        "## Features\n\n"
        "- Dynamic typing\n"
        "- Garbage collection\n"
        "- Multiple paradigms\n\n"
        "## Usage\n\n"
        "Python is used in web development, data science, and AI.\n"
        "It has a large ecosystem of libraries and frameworks.\n\n"
        "### Web Frameworks\n\n"
        "Django and Flask are popular web frameworks.\n"
        "They provide tools for building web applications.\n"
    )


@pytest.fixture
def sample_chunks(chunker: SmartChunker, sample_markdown: str) -> list[Chunk]:
    return chunker.chunk_text(sample_markdown, source="test.md")
