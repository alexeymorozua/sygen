#!/usr/bin/env python3
"""Web search via Perplexity Sonar API.

Usage:
    python perplexity_search.py --query "latest AI news" [--max-results 5]
    python perplexity_search.py --query "compare X and Y" --deep   # sonar-pro

Returns JSON with synthesized answer and sources.
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def search_perplexity(query: str, deep: bool = False) -> dict:
    try:
        import urllib.request
        import urllib.error

        api_key = os.environ.get("PPLX_API_KEY", "")
        if not api_key:
            return {"error": "PPLX_API_KEY not set"}

        model = "sonar-pro" if deep else "sonar"
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": query}],
        }).encode()

        req = urllib.request.Request(
            "https://api.perplexity.ai/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        answer = data["choices"][0]["message"]["content"]
        citations = data.get("citations", [])
        return {"answer": answer, "sources": citations, "model": model}

    except Exception as e:
        return {"error": str(e)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Web search via Perplexity Sonar")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--deep", action="store_true", help="Use sonar-pro for deeper research")
    args = parser.parse_args()

    result = search_perplexity(args.query, args.deep)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
