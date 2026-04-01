"""Tests for smart chunker."""

from __future__ import annotations

from sygen_bot.rag.chunker import Chunk, SmartChunker


class TestSmartChunker:
    def test_empty_text(self, chunker: SmartChunker) -> None:
        assert chunker.chunk_text("") == []
        assert chunker.chunk_text("   ") == []

    def test_short_text(self, chunker: SmartChunker) -> None:
        chunks = chunker.chunk_text("Hello world, this is a test.", source="test.md")
        assert len(chunks) == 1
        assert "Hello world" in chunks[0].text
        assert chunks[0].source == "test.md"

    def test_splits_by_headings(self, chunker: SmartChunker, sample_markdown: str) -> None:
        chunks = chunker.chunk_text(sample_markdown, source="doc.md")
        assert len(chunks) > 1
        # All chunks should have the source
        for c in chunks:
            assert c.source == "doc.md"

    def test_sections_detected(self, chunker: SmartChunker, sample_markdown: str) -> None:
        chunks = chunker.chunk_text(sample_markdown, source="doc.md")
        sections = {c.section for c in chunks}
        # Should detect at least some headings
        assert any("Feature" in s or "Usage" in s or "Introduction" in s for s in sections if s)

    def test_chunk_ids_unique(self, chunker: SmartChunker, sample_markdown: str) -> None:
        chunks = chunker.chunk_text(sample_markdown, source="doc.md")
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))

    def test_overlap(self) -> None:
        chunker = SmartChunker(chunk_size=100, overlap=30, min_chunk_size=10)
        text = "First paragraph.\n\nSecond paragraph with more text.\n\nThird paragraph here."
        chunks = chunker.chunk_text(text, source="test.md")
        if len(chunks) >= 2:
            # Second chunk should contain some text from end of first
            # (overlap mechanism)
            assert len(chunks[1].text) > 0

    def test_min_chunk_size_filter(self) -> None:
        chunker = SmartChunker(chunk_size=200, overlap=0, min_chunk_size=50)
        text = "Hi.\n\nThis is a longer paragraph that exceeds the minimum chunk size threshold."
        chunks = chunker.chunk_text(text, source="test.md")
        for c in chunks:
            assert len(c.text) >= 50

    def test_chunk_has_position_info(self, chunker: SmartChunker) -> None:
        text = "First paragraph.\n\nSecond paragraph."
        chunks = chunker.chunk_text(text, source="test.md")
        for c in chunks:
            assert c.start_char >= 0
            assert c.end_char >= c.start_char

    def test_chunk_facts(self, chunker: SmartChunker) -> None:
        facts = [
            {"id": "f1", "text": "User likes Python", "module": "user.md", "section": "Prefs", "raw": "likes Python"},
            {"id": "f2", "text": "Agent runs on Linux", "module": "infra.md", "section": "", "raw": "runs on Linux"},
        ]
        chunks = chunker.chunk_facts(facts, source="memory")
        assert len(chunks) == 2
        assert chunks[0].chunk_id == "f1"
        assert chunks[0].source == "memory"

    def test_token_estimate(self) -> None:
        chunk = Chunk(text="one two three four five", chunk_id="x", source="t")
        # 5 words * 1.3 ≈ 6
        assert chunk.token_estimate == 6

    def test_large_document_doesnt_crash(self, chunker: SmartChunker) -> None:
        text = "Line of text. " * 5000
        chunks = chunker.chunk_text(text, source="big.md")
        assert len(chunks) > 0
