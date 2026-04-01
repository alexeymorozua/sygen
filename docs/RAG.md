# Advanced RAG Pipeline

Hybrid retrieval-augmented generation with ColBERT v2 reranking, BM25 + vector search, and smart chunking. Fully local, no API keys required.

## Quick Start

1. Install dependencies:
```bash
pip install sygen[rag]
```

2. Enable in `config.json`:
```json
{
  "rag": {
    "enabled": true
  }
}
```

3. Restart the bot. RAG initializes lazily on the first message.

## How It Works

```
User Message
    |
    v
Query Expansion (keyword extraction, bigrams)
    |
    v
+---+---+
|       |
BM25    Vector Search
|       | (ChromaDB)
+---+---+
    |
    v
RRF Fusion (Reciprocal Rank Fusion)
    |
    v
ColBERT v2 Reranking (multilingual)
    |
    v
Context Injection (into system prompt)
```

Each user message triggers the pipeline automatically. Relevant context from memory and workspace files is injected into the agent's prompt.

## Components

### Smart Chunking

Documents are split into semantic chunks respecting natural boundaries:
- Paragraph breaks (double newlines)
- Markdown headings
- Sentence endings
- Configurable overlap between chunks

```json
{
  "rag": {
    "chunk_size": 512,
    "chunk_overlap": 64,
    "min_chunk_size": 50
  }
}
```

### Hybrid Search (BM25 + Vector)

Two search methods run in parallel:

- **BM25** (keyword-based): Catches exact term matches that embeddings miss. Uses `rank_bm25` (pure Python).
- **Vector** (semantic): ChromaDB with `paraphrase-multilingual-MiniLM-L12-v2` embeddings. Catches meaning even when words differ.

Results are fused using **Reciprocal Rank Fusion (RRF)** — a proven method from the original paper that combines rankings without needing score normalization.

```json
{
  "rag": {
    "bm25_weight": 0.4,
    "vector_weight": 0.6,
    "top_k_retrieval": 20
  }
}
```

### ColBERT v2 Reranking

After hybrid search, top results are reranked using ColBERT v2 late interaction:

1. Query and document tokens are encoded independently
2. MaxSim computes relevance (max similarity per query token)
3. Batched inference — all documents in one forward pass

**Model:** `antoinelouis/colbert-xm` (~560MB, multilingual, 50+ languages)

**Fallback chain:**
1. ColBERT v2 (best quality)
2. Cross-encoder `mmarco-mMiniLMv2-L12-H384-v1` (lighter, still multilingual)
3. No reranking (passthrough)

GPU is auto-detected (CUDA > MPS > CPU).

```json
{
  "rag": {
    "reranker_enabled": true,
    "reranker_model": "antoinelouis/colbert-xm",
    "reranker_top_k": 5
  }
}
```

To disable reranking (e.g., on Raspberry Pi):
```json
{
  "rag": {
    "reranker_enabled": false
  }
}
```

### Query Expansion

Queries are expanded for broader recall:
- **Keywords only** — stopwords removed (EN, RU, DE)
- **Bigrams** — key phrase extraction

All methods are local, language-agnostic, and add no latency.

```json
{
  "rag": {
    "query_expansion_enabled": true,
    "max_query_variants": 3
  }
}
```

### Multi-Source Indexing

The pipeline indexes:
- **Memory modules** (`memory_system/modules/*.md`)
- **Workspace files** (markdown, YAML, text)

Incremental reindexing — only changed files are re-processed.

```json
{
  "rag": {
    "index_workspace": true,
    "index_memory": true,
    "workspace_glob_patterns": ["*.md", "*.yaml", "*.yml", "*.txt"],
    "workspace_exclude_patterns": ["vector_db/**", "__pycache__/**"]
  }
}
```

### Result Cache

LRU cache avoids redundant searches for repeated queries.

```json
{
  "rag": {
    "cache_size": 128,
    "cache_ttl_seconds": 300
  }
}
```

## Full Configuration Reference

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `false` | Enable the RAG pipeline |
| `chunk_size` | `512` | Target chunk size in characters |
| `chunk_overlap` | `64` | Overlap between consecutive chunks |
| `min_chunk_size` | `50` | Minimum chunk size (smaller fragments merged) |
| `bm25_weight` | `0.4` | Weight for BM25 in RRF fusion |
| `vector_weight` | `0.6` | Weight for vector search in RRF fusion |
| `top_k_retrieval` | `20` | Candidates from hybrid search |
| `top_k_final` | `5` | Final results after reranking |
| `reranker_enabled` | `true` | Enable ColBERT/cross-encoder reranking |
| `reranker_model` | `antoinelouis/colbert-xm` | Reranker model name |
| `reranker_top_k` | `5` | Top results from reranker |
| `query_expansion_enabled` | `true` | Enable query expansion |
| `max_query_variants` | `3` | Max query variants including original |
| `cache_size` | `128` | LRU cache capacity |
| `cache_ttl_seconds` | `300` | Cache entry TTL (0 = no expiry) |
| `max_context_tokens` | `2000` | Max tokens injected into prompt |
| `index_workspace` | `true` | Index workspace files |
| `index_memory` | `true` | Index memory modules |
| `embedding_model` | `""` | Embedding model (empty = inherit from `memory.vector_model`) |

## Dependencies

All free, local, no API keys:

| Package | Size | Purpose |
|---------|------|---------|
| `rank-bm25` | ~15KB | BM25 keyword search |
| `chromadb` | ~50MB | Vector database |
| `sentence-transformers` | ~100MB | Embeddings + cross-encoder |
| `transformers` | ~200MB | ColBERT model loading |
| `torch` | ~800MB | Neural network inference |

**Models (downloaded on first use):**

| Model | Size | Purpose |
|-------|------|---------|
| `paraphrase-multilingual-MiniLM-L12-v2` | ~120MB | Embeddings (50+ languages) |
| `antoinelouis/colbert-xm` | ~560MB | ColBERT reranker |

## Architecture

```
sygen_bot/rag/
├── __init__.py          # Public API exports
├── config.py            # RAGConfig (Pydantic model)
├── chunker.py           # SmartChunker — semantic text splitting
├── bm25.py              # BM25Index — keyword search
├── retrieval.py         # HybridRetriever + RRF fusion
├── reranker.py          # ColBERTReranker (+ cross-encoder fallback)
├── query_expansion.py   # Query expansion (keywords, bigrams)
├── indexer.py           # MultiSourceIndexer — workspace/memory indexing
├── cache.py             # RAGCache — LRU with TTL
└── pipeline.py          # RAGPipeline — orchestrates all components
```

## Priority Chain

Context injection follows this priority:

1. **RAG Pipeline** (if enabled) — hybrid search + reranking
2. **Vector search** (if `memory.vector_search` enabled) — basic ChromaDB
3. **Module dump** — raw memory module content (fallback)
