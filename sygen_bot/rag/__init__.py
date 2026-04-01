"""Advanced RAG pipeline — hybrid search, ColBERT reranking, smart chunking.

Public API
----------
- ``RAGPipeline`` — main entry point for retrieval-augmented generation
- ``SmartChunker`` — semantic text chunking with overlap
- ``RAGConfig`` — configuration model
"""

from sygen_bot.rag.chunker import SmartChunker
from sygen_bot.rag.config import RAGConfig
from sygen_bot.rag.pipeline import RAGPipeline

__all__ = [
    "RAGConfig",
    "RAGPipeline",
    "SmartChunker",
]
