#!/usr/bin/env python3
"""Web search — Perplexity Sonar (primary) with DuckDuckGo fallback.

Usage:
    python web_search.py --query "latest AI news" [--max-results 5] [--region wt-wt]
    python web_search.py --query "Kotlin 2.2" --news          # news search
    python web_search.py --query "Claude API" --max-results 3  # limit results
    python web_search.py --query "test" --ddg                  # force DuckDuckGo

Primary engine: Perplexity Sonar API (PPLX_API_KEY from ~/.sygen/.env).
Returns: {answer, sources, engine: "perplexity"} — synthesized answer + source URLs.

Fallback (on error or --ddg): DuckDuckGo.
Returns: {results: [{title, url, body}], engine: "duckduckgo"} — list of links.

Agents should check "engine" field to know which format they received.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Load .env if PPLX_API_KEY not in environment
if not os.environ.get("PPLX_API_KEY"):
    _env_path = os.path.expanduser("~/.sygen/.env")
    if os.path.exists(_env_path):
        with open(_env_path) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _key, _, _val = _line.partition("=")
                    _key = _key.replace("export ", "").strip()
                    _val = _val.strip().strip('"').strip("'")
                    if _key and _key not in os.environ:
                        os.environ[_key] = _val

# Track fallback notifications to avoid spam
_fallback_notified = False


def _search_perplexity(query: str, news: bool = False) -> dict:
    """Search via Perplexity Sonar API. Returns {answer, sources, engine}."""
    import urllib.request
    import urllib.error

    api_key = os.environ.get("PPLX_API_KEY", "")
    if not api_key:
        raise RuntimeError("PPLX_API_KEY not set")

    prompt = query
    if news:
        prompt = f"Latest news: {query}"

    payload = json.dumps({
        "model": "sonar",
        "messages": [{"role": "user", "content": prompt}],
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

    return {
        "answer": answer,
        "sources": citations,
        "engine": "perplexity",
    }


def _search_ddg(query: str, max_results: int = 5, region: str = "wt-wt",
                news: bool = False) -> dict:
    """Search via DuckDuckGo. Returns {results: [{title, url, body}], engine}."""
    from ddgs import DDGS

    with DDGS() as ddgs:
        if news:
            results = list(ddgs.news(query, region=region, max_results=max_results))
        else:
            results = list(ddgs.text(query, region=region, max_results=max_results))

    return {
        "results": results,
        "engine": "duckduckgo",
    }


def _notify_fallback(error: str) -> None:
    """Send a notification to Server topic when Perplexity fails (once per session)."""
    global _fallback_notified
    if _fallback_notified:
        return
    _fallback_notified = True
    import urllib.request
    try:
        config_path = os.path.expanduser("~/.sygen/config/config.json")
        with open(config_path) as f:
            token = json.load(f).get("telegram_token", "")
        if not token:
            return
        msg = f"⚠️ <b>Perplexity API fallback</b>\n\nПоиск переключился на DuckDuckGo.\nОшибка: <code>{error[:200]}</code>"
        payload = json.dumps({
            "chat_id": -1003780548550,
            "message_thread_id": 68,
            "text": msg,
            "parse_mode": "HTML",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def search(query: str, max_results: int = 5, region: str = "wt-wt",
           news: bool = False, force_ddg: bool = False) -> dict:
    """Unified search: Perplexity first, DuckDuckGo fallback."""
    if not force_ddg:
        try:
            return _search_perplexity(query, news=news)
        except Exception as e:
            _notify_fallback(str(e))

    return _search_ddg(query, max_results, region, news)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Web search (Perplexity primary, DuckDuckGo fallback)")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--max-results", type=int, default=5,
                        help="Max results for DDG fallback (default 5)")
    parser.add_argument("--region", default="wt-wt",
                        help="Region for DDG fallback (wt-wt=global, ru-ru, ua-uk, us-en)")
    parser.add_argument("--news", action="store_true", help="Search news instead of web")
    parser.add_argument("--ddg", action="store_true",
                        help="Force DuckDuckGo (bypass Perplexity)")
    args = parser.parse_args()

    try:
        result = search(args.query, args.max_results, args.region, args.news, args.ddg)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
