"""Tests for vector memory store."""

from __future__ import annotations

from pathlib import Path

import pytest

from sygen_bot.memory.vector import (
    is_available,
    parse_facts_from_module,
)


# ---------------------------------------------------------------------------
# Fact parsing (no chromadb needed)
# ---------------------------------------------------------------------------


class TestParseFactsFromModule:
    def test_simple_list(self) -> None:
        content = "# Profile\n\n- Name: Alex\n- Role: Developer"
        facts = parse_facts_from_module(content, "user.md")
        assert len(facts) == 2
        assert facts[0]["raw"] == "Name: Alex"
        assert facts[0]["module"] == "user.md"
        assert facts[0]["section"] == "Profile"
        assert "[user.md] Profile: Name: Alex" in facts[0]["text"]

    def test_multiple_sections(self) -> None:
        content = (
            "# Identity\n"
            "- Name: Alex\n"
            "## Preferences\n"
            "- Language: Russian\n"
            "- Timezone: Europe/Kyiv\n"
        )
        facts = parse_facts_from_module(content, "user.md")
        assert len(facts) == 3
        assert facts[0]["section"] == "Identity"
        assert facts[1]["section"] == "Preferences"
        assert facts[2]["section"] == "Preferences"

    def test_empty_content(self) -> None:
        assert parse_facts_from_module("", "test.md") == []

    def test_no_list_items(self) -> None:
        content = "# Title\n\nJust some text without list items."
        assert parse_facts_from_module(content, "test.md") == []

    def test_unique_ids(self) -> None:
        content = "- Fact one\n- Fact two\n- Fact three"
        facts = parse_facts_from_module(content, "test.md")
        ids = {f["id"] for f in facts}
        assert len(ids) == 3  # all unique

    def test_asterisk_list_items(self) -> None:
        content = "* Item with asterisk\n* Another item"
        facts = parse_facts_from_module(content, "test.md")
        assert len(facts) == 2


# ---------------------------------------------------------------------------
# VectorMemoryStore (requires chromadb)
# ---------------------------------------------------------------------------

chromadb_available = is_available()
skip_no_chromadb = pytest.mark.skipif(
    not chromadb_available, reason="chromadb not installed"
)


@skip_no_chromadb
class TestVectorMemoryStore:
    def test_reindex_and_search(self, tmp_path: Path) -> None:
        from sygen_bot.memory.vector import VectorMemoryStore

        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()
        (modules_dir / "user.md").write_text(
            "# Profile\n- Name: Alex\n- Role: Developer\n- City: Kyiv"
        )
        (modules_dir / "decisions.md").write_text(
            "# Rules\n- Always run tests before push\n- Install only via pip"
        )

        store = VectorMemoryStore(tmp_path / "vector_db", model_name="default")
        count = store.reindex_modules(modules_dir)
        assert count == 5
        assert store.count == 5

        results = store.search("testing workflow", n_results=2)
        assert len(results) > 0
        # "Always run tests before push" should be most relevant
        assert any("test" in r["raw"].lower() for r in results)

    def test_search_formatted(self, tmp_path: Path) -> None:
        from sygen_bot.memory.vector import VectorMemoryStore

        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()
        (modules_dir / "user.md").write_text("# Info\n- Python developer since 2015")

        store = VectorMemoryStore(tmp_path / "vector_db", model_name="default")
        store.reindex_modules(modules_dir)

        formatted = store.search_formatted("programming experience")
        assert "Relevant Memory Facts" in formatted
        assert "Python developer" in formatted

    def test_empty_store_search(self, tmp_path: Path) -> None:
        from sygen_bot.memory.vector import VectorMemoryStore

        store = VectorMemoryStore(tmp_path / "vector_db", model_name="default")
        assert store.search("anything") == []
        assert store.search_formatted("anything") == ""

    def test_reindex_clears_old(self, tmp_path: Path) -> None:
        from sygen_bot.memory.vector import VectorMemoryStore

        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()
        (modules_dir / "user.md").write_text("- Old fact")

        store = VectorMemoryStore(tmp_path / "vector_db", model_name="default")
        store.reindex_modules(modules_dir)
        assert store.count == 1

        (modules_dir / "user.md").write_text("- New fact one\n- New fact two")
        store.reindex_modules(modules_dir)
        assert store.count == 2


# ---------------------------------------------------------------------------
# Graceful fallback when chromadb not installed
# ---------------------------------------------------------------------------


def test_search_memory_vector_no_chromadb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """search_memory_vector returns empty string when chromadb unavailable."""
    from sygen_bot.memory import vector as vec_mod
    from sygen_bot.workspace.loader import search_memory_vector

    # Force chromadb unavailable
    monkeypatch.setattr(vec_mod, "_chromadb_available", False)
    monkeypatch.setattr(vec_mod, "_store", None)
    monkeypatch.setattr(vec_mod, "_store_init_failed", False)

    result = search_memory_vector(
        "test query",
        tmp_path / "vector_db",
        tmp_path / "modules",
    )
    assert result == ""
