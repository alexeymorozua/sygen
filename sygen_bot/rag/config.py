"""RAG pipeline configuration."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RAGConfig(BaseModel):
    """Configuration for the Advanced RAG pipeline.

    All models are free/local — no API keys required.
    """

    enabled: bool = False

    # --- Chunking ---
    chunk_size: int = Field(default=512, ge=64, le=4096)
    chunk_overlap: int = Field(default=64, ge=0, le=512)
    min_chunk_size: int = Field(default=50, ge=10)

    # --- Retrieval ---
    bm25_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    vector_weight: float = Field(default=0.6, ge=0.0, le=1.0)
    top_k_retrieval: int = Field(default=20, ge=1, le=100)
    top_k_final: int = Field(default=5, ge=1, le=50)

    # --- Reranker ---
    reranker_enabled: bool = True
    reranker_model: str = "antoinelouis/colbert-xm"
    reranker_top_k: int = Field(default=5, ge=1, le=50)

    # --- Embedding (inherits from memory config if empty) ---
    embedding_model: str = ""  # empty = use memory.vector_model

    # --- Query expansion ---
    query_expansion_enabled: bool = True
    max_query_variants: int = Field(default=3, ge=1, le=10)

    # --- Cache ---
    cache_size: int = Field(default=128, ge=0, le=10000)
    cache_ttl_seconds: int = Field(default=300, ge=0)

    # --- Multi-source ---
    index_workspace: bool = True
    index_memory: bool = True
    workspace_glob_patterns: list[str] = Field(
        default_factory=lambda: ["*.md", "*.yaml", "*.yml", "*.txt"],
    )
    workspace_exclude_patterns: list[str] = Field(
        default_factory=lambda: ["vector_db/**", "__pycache__/**", "*.pyc"],
    )

    # --- Injection ---
    max_context_tokens: int = Field(default=2000, ge=100, le=16000)
    injection_header: str = "# Retrieved Context"
