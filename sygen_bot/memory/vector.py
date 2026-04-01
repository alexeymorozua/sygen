"""Vector memory store for semantic search over memory facts.

Optional feature — requires ``chromadb`` (``pip install sygen[vector]``).
When sentence-transformers is also installed, uses a multilingual model
for better non-English retrieval.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

_chromadb_available: bool | None = None


def is_available() -> bool:
    """Return True if chromadb is importable."""
    global _chromadb_available
    if _chromadb_available is None:
        try:
            import chromadb as _  # noqa: F811, F401
            _chromadb_available = True
        except ImportError:
            _chromadb_available = False
    return _chromadb_available


# ---------------------------------------------------------------------------
# Embedding function resolution
# ---------------------------------------------------------------------------

_DEFAULT_MULTILINGUAL_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
_DEFAULT_EN_MODEL = "all-MiniLM-L6-v2"


def _resolve_embedding_fn(model_name: str | None = None):  # type: ignore[no-untyped-def]
    """Pick the best available embedding function.

    Priority:
    1. sentence-transformers with user-specified or multilingual model
    2. chromadb built-in ONNX (English, no extra deps)
    """
    import chromadb.utils.embedding_functions as ef

    # Try sentence-transformers for multilingual support
    if model_name != "default":
        try:
            chosen = model_name or _DEFAULT_MULTILINGUAL_MODEL
            fn = ef.SentenceTransformerEmbeddingFunction(model_name=chosen)
            logger.info("Vector memory: using sentence-transformers model '%s'", chosen)
            return fn
        except (ImportError, Exception) as exc:
            logger.debug("sentence-transformers not available (%s), falling back to ONNX", exc)

    # Fallback: built-in ONNX (English-focused, no torch needed)
    logger.info("Vector memory: using built-in ONNX model (%s)", _DEFAULT_EN_MODEL)
    return ef.ONNXMiniLM_L6_V2()


# ---------------------------------------------------------------------------
# Fact parsing
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^#{1,4}\s+(.+)", re.MULTILINE)
_LIST_ITEM_RE = re.compile(r"^[-*]\s+(.+)", re.MULTILINE)


def parse_facts_from_module(content: str, module_name: str) -> list[dict[str, str]]:
    """Extract discrete facts from a markdown memory module.

    Each list item (``- fact``) becomes a separate fact entry.
    Headings provide context metadata.
    """
    facts: list[dict[str, str]] = []
    current_section = ""

    for line in content.splitlines():
        heading_m = _HEADING_RE.match(line)
        if heading_m:
            current_section = heading_m.group(1).strip()
            continue

        item_m = _LIST_ITEM_RE.match(line)
        if item_m:
            fact_text = item_m.group(1).strip()
            if not fact_text:
                continue
            # Combine section context with fact for better embedding
            if current_section:
                full_text = f"[{module_name}] {current_section}: {fact_text}"
            else:
                full_text = f"[{module_name}] {fact_text}"
            fact_id = hashlib.md5(full_text.encode()).hexdigest()[:12]
            facts.append({
                "id": fact_id,
                "text": full_text,
                "module": module_name,
                "section": current_section,
                "raw": fact_text,
            })

    return facts


# ---------------------------------------------------------------------------
# VectorMemoryStore
# ---------------------------------------------------------------------------

_COLLECTION_NAME = "sygen_memory"


class VectorMemoryStore:
    """Persistent vector store for memory facts.

    Uses ChromaDB with automatic embedding. Falls back gracefully
    when chromadb is not installed.

    Args:
        persist_dir: Directory for ChromaDB persistent storage.
        model_name: Embedding model name, or ``"default"`` for built-in ONNX.
    """

    def __init__(self, persist_dir: Path, model_name: str | None = None) -> None:
        import chromadb

        self._persist_dir = persist_dir
        persist_dir.mkdir(parents=True, exist_ok=True)

        embedding_fn = _resolve_embedding_fn(model_name)
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "VectorMemoryStore ready: %d facts indexed, persist=%s",
            self._collection.count(),
            persist_dir,
        )

    @property
    def count(self) -> int:
        """Number of indexed facts."""
        return self._collection.count()

    def reindex_modules(self, modules_dir: Path) -> int:
        """Reindex all memory modules from disk.

        Clears existing index and re-parses all .md files.
        Returns the number of facts indexed.
        """
        # Clear existing
        existing = self._collection.get()
        if existing["ids"]:
            self._collection.delete(ids=existing["ids"])

        all_facts: list[dict[str, str]] = []
        for md_file in sorted(modules_dir.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
            except OSError:
                continue
            if not content.strip():
                continue
            facts = parse_facts_from_module(content, md_file.name)
            all_facts.extend(facts)

        if not all_facts:
            return 0

        self._collection.add(
            ids=[f["id"] for f in all_facts],
            documents=[f["text"] for f in all_facts],
            metadatas=[
                {"module": f["module"], "section": f["section"], "raw": f["raw"]}
                for f in all_facts
            ],
        )
        logger.info("Reindexed %d facts from %s", len(all_facts), modules_dir)
        return len(all_facts)

    def search(
        self,
        query: str,
        n_results: int = 5,
        module_filter: str | None = None,
    ) -> list[dict[str, str]]:
        """Search for facts semantically similar to query.

        Returns list of dicts with 'text', 'module', 'section', 'raw', 'distance'.
        """
        if self._collection.count() == 0:
            return []

        where = {"module": module_filter} if module_filter else None
        n = min(n_results, self._collection.count())

        results = self._collection.query(
            query_texts=[query],
            n_results=n,
            where=where,
        )

        facts: list[dict[str, str]] = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                dist = results["distances"][0][i] if results["distances"] else 0.0
                facts.append({
                    "text": doc,
                    "module": meta.get("module", ""),
                    "section": meta.get("section", ""),
                    "raw": meta.get("raw", doc),
                    "distance": str(round(dist, 4)),
                })
        return facts

    def search_formatted(
        self,
        query: str,
        n_results: int = 5,
    ) -> str:
        """Search and return formatted string for prompt injection."""
        facts = self.search(query, n_results=n_results)
        if not facts:
            return ""
        lines = ["# Relevant Memory Facts"]
        for f in facts:
            lines.append(f"- {f['raw']}  _(from {f['module']})_")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Module-level singleton (lazy init)
# ---------------------------------------------------------------------------

_store: VectorMemoryStore | None = None
_store_init_failed: bool = False


def get_store(persist_dir: Path, model_name: str | None = None) -> VectorMemoryStore | None:
    """Get or create the singleton VectorMemoryStore.

    Returns None if chromadb is not installed or init fails.
    """
    global _store, _store_init_failed
    if _store is not None:
        return _store
    if _store_init_failed:
        return None
    if not is_available():
        return None
    try:
        _store = VectorMemoryStore(persist_dir, model_name=model_name)
        return _store
    except Exception:
        logger.warning("Failed to initialize VectorMemoryStore", exc_info=True)
        _store_init_failed = True
        return None
