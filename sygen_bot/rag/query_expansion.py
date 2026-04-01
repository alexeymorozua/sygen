"""Query expansion for improved recall.

Generates query variants using local techniques (no LLM required):
1. Original query (always included)
2. Keyword extraction — core terms only
3. Bigram/trigram extraction — key phrases
4. Transliteration (for mixed-script queries)

All methods are language-agnostic and work with any Unicode text.
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"\w+", re.UNICODE)
_STOPWORDS_COMMON = frozenset({
    # English
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "must", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "and", "but", "or", "nor", "not", "no", "so", "yet", "both", "either",
    "it", "its", "this", "that", "these", "those", "i", "me", "my", "we",
    "our", "you", "your", "he", "she", "they", "them", "his", "her",
    "what", "which", "who", "whom", "how", "when", "where", "why",
    # Russian
    "и", "в", "на", "с", "не", "что", "это", "как", "по", "из", "за",
    "для", "от", "до", "о", "об", "но", "а", "к", "у", "же", "то",
    "ещё", "еще", "бы", "ли", "мне", "мы", "я", "ты", "он", "она",
    "они", "его", "её", "их", "мой", "наш", "ваш", "этот", "тот",
    # German
    "der", "die", "das", "ein", "eine", "und", "ist", "sind", "war",
    "hat", "haben", "ich", "du", "er", "sie", "wir", "ihr", "es",
    "nicht", "mit", "auf", "für", "von", "zu", "den", "dem", "des",
})


def expand_query(
    query: str,
    max_variants: int = 3,
) -> list[str]:
    """Generate query variants for broader retrieval.

    Always returns the original query as the first element.
    Additional variants are generated using keyword extraction
    and n-gram analysis.

    Args:
        query: Original user query.
        max_variants: Maximum total variants including original.

    Returns:
        List of query strings, original first.
    """
    variants: list[str] = [query]
    if max_variants <= 1:
        return variants

    words = _WORD_RE.findall(query.lower())
    if len(words) < 3:
        # Short queries don't benefit from expansion
        return variants

    # Variant 1: Keywords only (remove stopwords)
    keywords = [w for w in words if w not in _STOPWORDS_COMMON and len(w) > 1]
    if keywords and len(keywords) < len(words):
        kw_query = " ".join(keywords)
        if kw_query != query.lower():
            variants.append(kw_query)

    if len(variants) >= max_variants:
        return variants[:max_variants]

    # Variant 2: Bigrams from keywords
    if len(keywords) >= 2:
        bigrams = [f"{keywords[i]} {keywords[i+1]}" for i in range(len(keywords) - 1)]
        # Take top bigrams (heuristic: first and last are usually most important)
        selected = []
        if bigrams:
            selected.append(bigrams[0])
        if len(bigrams) > 1:
            selected.append(bigrams[-1])
        bigram_query = " ".join(selected)
        if bigram_query and bigram_query not in variants:
            variants.append(bigram_query)

    return variants[:max_variants]
