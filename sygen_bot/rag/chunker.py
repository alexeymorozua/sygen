"""Smart semantic chunker with overlap and boundary detection.

Splits documents into chunks that respect natural boundaries:
- Paragraph breaks (double newlines)
- Markdown headings
- Sentence endings
- List item boundaries

Each chunk carries metadata about its source for attribution.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class Chunk:
    """A single text chunk with source metadata."""

    text: str
    chunk_id: str
    source: str  # file path or module name
    section: str = ""  # nearest heading above the chunk
    start_char: int = 0
    end_char: int = 0
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def token_estimate(self) -> int:
        """Rough token count (words * 1.3)."""
        return int(len(self.text.split()) * 1.3)


class SmartChunker:
    """Semantic-aware text chunker.

    Splits text into chunks of approximately ``chunk_size`` characters,
    with ``overlap`` characters of overlap between consecutive chunks.
    Respects natural text boundaries (paragraphs, headings, sentences).

    Args:
        chunk_size: Target chunk size in characters.
        overlap: Overlap between consecutive chunks in characters.
        min_chunk_size: Minimum chunk size; smaller fragments merge with neighbors.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int = 64,
        min_chunk_size: int = 50,
    ) -> None:
        self.chunk_size = chunk_size
        self.overlap = min(overlap, chunk_size // 2)
        self.min_chunk_size = min_chunk_size

    def chunk_text(self, text: str, source: str = "") -> list[Chunk]:
        """Split text into semantic chunks.

        Steps:
        1. Split into sections by headings
        2. Within each section, split by paragraphs
        3. Merge small paragraphs, split large ones
        4. Apply overlap between consecutive chunks
        """
        if not text or not text.strip():
            return []

        sections = self._split_by_headings(text)
        raw_chunks: list[tuple[str, str, int]] = []  # (text, section, start_char)

        for section_title, section_text, section_start in sections:
            paragraphs = self._split_by_paragraphs(section_text, section_start)
            merged = self._merge_small_paragraphs(paragraphs)
            for para_text, para_start in merged:
                if len(para_text) <= self.chunk_size:
                    raw_chunks.append((para_text, section_title, para_start))
                else:
                    # Split oversized paragraphs by sentences
                    sub_chunks = self._split_large_block(
                        para_text, para_start,
                    )
                    for sc_text, sc_start in sub_chunks:
                        raw_chunks.append((sc_text, section_title, sc_start))

        # Apply overlap
        chunks = self._apply_overlap(raw_chunks, text)

        # Build Chunk objects
        result: list[Chunk] = []
        for chunk_text, section, start in chunks:
            chunk_text = chunk_text.strip()
            if len(chunk_text) < self.min_chunk_size:
                continue
            chunk_id = hashlib.md5(
                f"{source}:{start}:{chunk_text[:64]}".encode(),
            ).hexdigest()[:12]
            result.append(Chunk(
                text=chunk_text,
                chunk_id=chunk_id,
                source=source,
                section=section,
                start_char=start,
                end_char=start + len(chunk_text),
            ))
        return result

    def chunk_file(self, path: Path) -> list[Chunk]:
        """Chunk a file from disk."""
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return []
        return self.chunk_text(text, source=str(path))

    def chunk_facts(
        self, facts: list[dict[str, str]], source: str = "memory",
    ) -> list[Chunk]:
        """Chunk pre-parsed memory facts (from vector.py format).

        Each fact becomes its own chunk (facts are already atomic).
        """
        chunks: list[Chunk] = []
        for i, fact in enumerate(facts):
            text = fact.get("text", fact.get("raw", ""))
            if not text.strip():
                continue
            chunk_id = fact.get("id", hashlib.md5(
                text.encode(),
            ).hexdigest()[:12])
            chunks.append(Chunk(
                text=text,
                chunk_id=chunk_id,
                source=source,
                section=fact.get("section", ""),
                start_char=i,
                end_char=i + 1,
                metadata={"module": fact.get("module", "")},
            ))
        return chunks

    # ------------------------------------------------------------------
    # Internal splitting
    # ------------------------------------------------------------------

    def _split_by_headings(
        self, text: str,
    ) -> list[tuple[str, str, int]]:
        """Split text by markdown headings.

        Returns: [(section_title, section_text, start_char), ...]
        """
        heading_positions: list[tuple[int, str]] = []
        for m in _HEADING_RE.finditer(text):
            line_end = text.find("\n", m.start())
            if line_end == -1:
                line_end = len(text)
            title = text[m.start():line_end].lstrip("#").strip()
            heading_positions.append((m.start(), title))

        if not heading_positions:
            return [("", text, 0)]

        sections: list[tuple[str, str, int]] = []

        # Text before first heading
        if heading_positions[0][0] > 0:
            pre = text[:heading_positions[0][0]]
            if pre.strip():
                sections.append(("", pre, 0))

        for idx, (pos, title) in enumerate(heading_positions):
            end = heading_positions[idx + 1][0] if idx + 1 < len(heading_positions) else len(text)
            section_text = text[pos:end]
            sections.append((title, section_text, pos))

        return sections

    def _split_by_paragraphs(
        self, text: str, base_offset: int,
    ) -> list[tuple[str, int]]:
        """Split by double newlines. Returns [(text, start_char), ...]."""
        parts: list[tuple[str, int]] = []
        last_end = 0
        for m in _PARAGRAPH_BREAK.finditer(text):
            chunk = text[last_end:m.start()]
            if chunk.strip():
                parts.append((chunk, base_offset + last_end))
            last_end = m.end()
        # Remainder
        remainder = text[last_end:]
        if remainder.strip():
            parts.append((remainder, base_offset + last_end))
        return parts if parts else [(text, base_offset)]

    def _merge_small_paragraphs(
        self, paragraphs: list[tuple[str, int]],
    ) -> list[tuple[str, int]]:
        """Merge consecutive small paragraphs into larger blocks."""
        if not paragraphs:
            return []
        merged: list[tuple[str, int]] = []
        current_text, current_start = paragraphs[0]

        for para_text, para_start in paragraphs[1:]:
            combined_len = len(current_text) + len(para_text) + 2  # +2 for \n\n
            if combined_len <= self.chunk_size:
                current_text = current_text + "\n\n" + para_text
            else:
                merged.append((current_text, current_start))
                current_text, current_start = para_text, para_start

        merged.append((current_text, current_start))
        return merged

    def _split_large_block(
        self, text: str, base_offset: int,
    ) -> list[tuple[str, int]]:
        """Split an oversized block by sentence boundaries."""
        sentences: list[tuple[str, int]] = []
        last_end = 0
        for m in _SENTENCE_END.finditer(text):
            sent = text[last_end:m.start() + 1]  # include punctuation
            if sent.strip():
                sentences.append((sent, base_offset + last_end))
            last_end = m.end()
        remainder = text[last_end:]
        if remainder.strip():
            sentences.append((remainder, base_offset + last_end))

        if not sentences:
            return [(text, base_offset)]

        # Greedily merge sentences up to chunk_size
        chunks: list[tuple[str, int]] = []
        current_text, current_start = sentences[0]
        for sent_text, sent_start in sentences[1:]:
            if len(current_text) + len(sent_text) + 1 <= self.chunk_size:
                current_text = current_text + " " + sent_text
            else:
                chunks.append((current_text, current_start))
                current_text, current_start = sent_text, sent_start
        chunks.append((current_text, current_start))
        return chunks

    def _apply_overlap(
        self,
        chunks: list[tuple[str, str, int]],
        original_text: str,
    ) -> list[tuple[str, str, int]]:
        """Add overlap text from the end of previous chunk to the start of next."""
        if self.overlap <= 0 or len(chunks) <= 1:
            return chunks

        result: list[tuple[str, str, int]] = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_text = chunks[i - 1][0]
            curr_text, section, start = chunks[i]

            # Take last `overlap` chars from previous chunk
            overlap_text = prev_text[-self.overlap:]
            # Find a clean break point (space, newline)
            clean_start = 0
            for j, ch in enumerate(overlap_text):
                if ch in (" ", "\n"):
                    clean_start = j + 1
                    break

            overlap_text = overlap_text[clean_start:]
            if overlap_text.strip():
                new_text = overlap_text + " " + curr_text
                new_start = max(0, start - len(overlap_text))
            else:
                new_text = curr_text
                new_start = start

            result.append((new_text, section, new_start))
        return result
